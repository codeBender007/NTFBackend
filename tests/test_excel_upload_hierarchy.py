"""Tests for Excel/CSV employee bulk upload hierarchy matching and foreign key ID assignment."""
from __future__ import annotations

import asyncio
import io
import os
import sys
import tempfile
from datetime import date, datetime

# Allow running directly without MSSQL env vars or pyodbc by setting dummy env defaults if needed.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.LMS.models.departmentsModel import Department
from app.LMS.models.linesModel import Line
from app.LMS.models.machineModel import Machine
from app.LMS.models.plantsModel import Plant
from app.LMS.models.roleModel import Role
from app.LMS.models.rolePermissionModel import RolePermission
from app.LMS.models.pageModel import Page
from app.LMS.models.subDepartmentsModel import SubDepartment
from app.LMS.models.userModel import User
from app.LMS.schemas.userSchema import ExcelUploadResponse, UserResponse
from app.LMS.services import userService


def _setup_db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _register_mssql_funcs(dbapi_conn, _conn_record):
        dbapi_conn.create_function("getdate", 0, lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed hierarchy mirroring production DB (including duplicate 'abc' names across departments)
    p1 = Plant(id=1, plantName="unit 5")
    p2 = Plant(id=16, plantName="Secure Gurugram Plant")
    db.add_all([p1, p2])
    db.flush()

    dept_specs = [
        (1, "ACCESSORIES"), (2, "ACCOUNTS"), (3, "ADMIN"), (4, "DISPATCH"),
        (5, "IT"), (6, "LB"), (7, "MAINTENANCE"), (8, "NBD"),
        (9, "OPERATIONS"), (10, "PAINT SHOP"), (11, "PIM"), (12, "QUALITY"),
        (13, "STORE"), (14, "TCM"), (15, "TOOL ROOM"), (16, "YED LINE"),
    ]
    for did, dname in dept_specs:
        db.add(Department(id=did, plantId=1, departmentName=dname))
    db.flush()

    # Duplicate 'abc' records across departments to verify parent-scoped disambiguation
    for idx, (did, _) in enumerate(dept_specs, start=10):
        sd_abc = SubDepartment(id=idx, plantId=1, departmentId=did, subDepartmentName="abc")
        ln_abc = Line(id=idx, plantId=1, departmentId=did, subDepartmentId=idx, lineName="abc")
        mc_abc = Machine(id=idx, plantId=1, departmentId=did, subDepartmentId=idx, lineId=idx, machineName="abc")
        db.add_all([sd_abc, ln_abc, mc_abc])

    # Specific *SubDep / *Line / *Machine records matching production DB
    for offset, (did, dname) in enumerate(dept_specs):
        prefix = dname.replace(" ", "")
        sd_id = 1009 + offset
        ln_id = 1008 + offset
        mc_id = 1003 + offset
        db.add(SubDepartment(id=sd_id, plantId=1, departmentId=did, subDepartmentName=f"{prefix}SubDep"))
        db.add(Line(id=ln_id, plantId=1, departmentId=did, subDepartmentId=sd_id, lineName=f"{prefix}Line"))
        db.add(Machine(
            id=mc_id, plantId=1, departmentId=did, subDepartmentId=sd_id, lineId=ln_id,
            machineName=f"{prefix}Machine",
        ))

    db.commit()
    return db


def _run_coro(coro):
    """Drive an in-memory coroutine without requiring a socket-backed asyncio loop."""
    try:
        coro.send(None)
    except StopIteration as stop:
        return stop.value
    raise RuntimeError("Coroutine yielded unexpectedly in synchronous test runner")


def _make_csv_upload(rows: list[dict], filename: str = "employees.csv") -> UploadFile:
    df = pd.DataFrame(rows)
    buf = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
    buf.write(df.to_csv(index=False).encode("utf-8"))
    buf.seek(0)
    return UploadFile(filename=filename, file=buf)


def test_full_hierarchy_matching_and_edge_cases():
    db = _setup_db()

    # Pre-existing employee (simulating re-upload that must preserve password/role)
    existing_user = User(
        payCode="10144",
        empName="Vishnu Old",
        dob=date(1980, 1, 1),
        departmentId=6,
        departmentName="LB",
        passwordHash="keep-this-hash",
        role="Line Leader",
        active=True,
    )
    db.add(existing_user)
    db.commit()

    rows = [
        # 1. Re-upload existing user with full hierarchy + trailing spaces
        {
            "Paycode": "10144",
            "EmployeeName": "Vishnu",
            "Date_Of_Birth": "01/01/1980",
            "Date_Of_Join": "01/11/2018",
            "Department": "LB   ",
            "SubDepartment": " LBSubDep ",
            "Line": "lbline",
            "Machine": "  LBMACHINE ",
            "Shift ": "B ",
            "Basic ": "18501",
            "HRA": "2000",
            "Active": "Y",
            "isDojo": "Yes",
        },
        # 2. Excel DISPACTH typo across all 4 hierarchy levels + mixed casing
        {
            "Paycode": "20001",
            "EmployeeName": "Dispatch Worker",
            "Date_Of_Birth": "15/05/1992",
            "Date_Of_Join": "01/06/2021",
            "Department": "  dispacth  ",
            "SubDepartment": "DISPACTHSubDep",
            "Line": " dispacthLine ",
            "Machine": "dispacthmachine",
            "Shift ": "A",
            "Basic ": "15000",
            "HRA": "1500",
            "Active": "Y",
            "isDojo": "No",
        },
        # 3. Duplicate name ('abc') disambiguated via parent Department (QUALITY id=12)
        {
            "Paycode": "20002",
            "EmployeeName": "Quality ABC Worker",
            "Date_Of_Birth": "10/10/1995",
            "Date_Of_Join": "01/01/2022",
            "Department": "quality",
            "SubDepartment": "  ABC ",
            "Line": "abc",
            "Machine": "ABC",
            "Shift ": "GEN",
            "Basic ": "16000",
            "HRA": "1000",
            "Active": "Y",
            "isDojo": "Yes",
        },
        # 4. Graceful handling: valid Dept & SubDept, unmatched Line & Machine -> row STILL inserted!
        {
            "Paycode": "20003",
            "EmployeeName": "Partial Match Worker",
            "Date_Of_Birth": "20/03/1990",
            "Date_Of_Join": "12/04/2022",
            "Department": "PAINT SHOP",
            "SubDepartment": "PAINT SHOP SubDep",  # spacing variation
            "Line": "NonExistentLine",
            "Machine": "NonExistentMachine",
            "Shift ": "A",
            "Basic ": "17000",
            "HRA": "1200",
            "Active": "Y",
            "isDojo": "No",
        },
        # 5. Graceful handling: completely missing/unmatched hierarchy -> row STILL inserted!
        {
            "Paycode": "20004",
            "EmployeeName": "Unmatched Dept Worker",
            "Date_Of_Birth": "05/07/1991",
            "Date_Of_Join": "01/02/2023",
            "Department": "Unknown Dept XYZ",
            "SubDepartment": "",
            "Line": "",
            "Machine": "",
            "Shift ": "B",
            "Basic ": "14000",
            "HRA": "800",
            "Active": "Y",
            "isDojo": "No",
        },
        # 6. Invalid row (empty EmployeeName) -> skipped without breaking valid rows
        {
            "Paycode": "20005",
            "EmployeeName": "",
            "Date_Of_Birth": "01/01/1990",
            "Date_Of_Join": "01/01/2020",
            "Department": "IT",
            "SubDepartment": "ITSubDep",
            "Line": "ITLine",
            "Machine": "ITMachine",
            "Shift ": "A",
            "Basic ": "10000",
            "HRA": "500",
            "Active": "Y",
            "isDojo": "No",
        },
    ]

    upload = _make_csv_upload(rows)
    res = _run_coro(userService.processExcelUpload(db, upload))
    validated = ExcelUploadResponse(**res)

    assert validated.inserted == 4, f"Expected 4 inserted, got {validated}"
    assert validated.updated == 1, f"Expected 1 updated, got {validated}"
    assert validated.skipped == 1, f"Expected 1 skipped, got {validated}"
    assert validated.errorCount == 1
    assert validated.warningCount >= 3

    # Verify Row 1 (updated existing user: IDs mapped, password & role preserved)
    u1 = db.query(User).filter(User.payCode == "10144").first()
    assert u1.plantId == 1
    assert u1.departmentId == 6 and u1.departmentName == "LB"
    assert u1.subDepartmentId == 1014 and u1.subDepartmentName == "LBSubDep"
    assert u1.lineId == 1013 and u1.lineName == "LBLine"
    assert u1.machineId == 1008 and u1.machineName == "LBMachine"
    assert u1.passwordHash == "keep-this-hash"
    assert u1.role == "Line Leader"

    # Verify Row 2 (DISPACTH alias matched to DISPATCH across all 4 levels)
    u2 = db.query(User).filter(User.payCode == "20001").first()
    assert u2.plantId == 1
    assert u2.departmentId == 4 and u2.departmentName == "DISPATCH"
    assert u2.subDepartmentId == 1012 and u2.subDepartmentName == "DISPATCHSubDep"
    assert u2.lineId == 1011 and u2.lineName == "DISPATCHLine"
    assert u2.machineId == 1006 and u2.machineName == "DISPATCHMachine"

    # Verify Row 3 (duplicate 'abc' resolved specifically under QUALITY dept 12)
    u3 = db.query(User).filter(User.payCode == "20002").first()
    assert u3.departmentId == 12
    sub_q = db.query(SubDepartment).filter(SubDepartment.id == u3.subDepartmentId).first()
    line_q = db.query(Line).filter(Line.id == u3.lineId).first()
    mach_q = db.query(Machine).filter(Machine.id == u3.machineId).first()
    assert sub_q.departmentId == 12
    assert line_q.subDepartmentId == u3.subDepartmentId
    assert mach_q.lineId == u3.lineId

    # Verify Row 4 (partial match: Dept & compact-matched SubDept saved; unmatched Line/Machine NULL)
    u4 = db.query(User).filter(User.payCode == "20003").first()
    assert u4.plantId == 1
    assert u4.departmentId == 10 and u4.departmentName == "PAINT SHOP"
    assert u4.subDepartmentId == 1018 and u4.subDepartmentName == "PAINTSHOPSubDep"
    assert u4.lineId is None and u4.lineName == "NonExistentLine"
    assert u4.machineId is None and u4.machineName == "NonExistentMachine"

    # Verify Row 5 (unmatched dept saved gracefully with NULL FKs)
    u5 = db.query(User).filter(User.payCode == "20004").first()
    assert u5 is not None
    assert u5.departmentId is None and u5.departmentName == "Unknown Dept XYZ"
    assert u5.subDepartmentId is None
    assert u5.lineId is None
    assert u5.machineId is None

    db.close()
    print("[OK] test_full_hierarchy_matching_and_edge_cases PASSED")


def test_flexible_column_headers_and_absent_lower_columns():
    db = _setup_db()
    # Pre-seed soft-deleted (active=False) user with existing subDepartmentId and non-RFC admin-like email
    # to ensure: (1) re-upload without SubDepartment doesn't wipe lower hierarchy,
    # (2) re-upload explicitly reactivates active=True even without an Active column,
    # (3) UserResponse serializes legacy non-RFC email strings (like 'admin') without 500 error.
    db.add(User(
        payCode="30001",
        empName="Existing",
        dob=date(1990, 1, 1),
        departmentId=5,
        departmentName="IT",
        subDepartmentId=1013,
        subDepartmentName="ITSubDep",
        lineId=1012,
        lineName="ITLine",
        machineId=1007,
        machineName="ITMachine",
        email="admin",
        passwordHash="hash",
        active=False,
    ))
    db.commit()

    # Upload with lowercase/underscore headers and NO SubDepartment/Line/Machine/Active columns
    upload = _make_csv_upload([
        {
            "pay_code": "30001",
            "employee_name": "Existing Renamed",
            "department_name": " it ",
        }
    ])
    res = _run_coro(userService.processExcelUpload(db, upload))
    assert res["updated"] == 1
    u = db.query(User).filter(User.payCode == "30001").first()
    assert u.empName == "Existing Renamed"
    assert u.departmentId == 5
    # Explicitly reactivated on upsert
    assert u.active is True
    # Existing lower hierarchy preserved because those columns were absent in the sheet
    assert u.subDepartmentId == 1013
    assert u.lineId == 1012
    assert u.machineId == 1007
    # UserResponse must serialize non-RFC email like 'admin' cleanly
    serialized = UserResponse.model_validate(u)
    assert serialized.email == "admin"
    assert serialized.active is True
    db.close()
    print("[OK] test_flexible_column_headers_and_absent_lower_columns PASSED")


if __name__ == "__main__":
    test_full_hierarchy_matching_and_edge_cases()
    test_flexible_column_headers_and_absent_lower_columns()
    print("ALL EXCEL HIERARCHY UPLOAD TESTS PASSED!")
