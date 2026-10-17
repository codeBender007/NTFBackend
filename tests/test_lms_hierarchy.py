"""
Comprehensive Test Suite for Modular LMS, Dashboard, and CMS Architecture.
"""
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base
from app.LMS.models.plantsModel import Plant
from app.LMS.models.departmentsModel import Department
from app.LMS.models.subDepartmentsModel import SubDepartment
from app.LMS.models.linesModel import Line
from app.LMS.models.machineModel import Machine

from app.LMS.schemas.plantsSchema import PlantCreate, PlantUpdate, PlantResponse
from app.LMS.schemas.departmentsSchema import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.LMS.schemas.subDepartmentsSchema import SubDepartmentCreate, SubDepartmentUpdate, SubDepartmentResponse
from app.LMS.schemas.linesSchema import LineCreate, LineUpdate, LineResponse
from app.LMS.schemas.machineSchema import MachineCreate, MachineUpdate, MachineResponse

from app.LMS.services import (
    plantsService,
    departmentsService,
    subDepartmentsService,
    linesService,
    machineService,
)

def run_all_tests():
    print("==================================================")
    print("  RUNNING MODULAR ARCHITECTURE VERIFICATION TEST  ")
    print("==================================================")

    # 1. Verify OpenAPI routes & Module Prefixes
    schema = app.openapi()
    paths = schema["paths"]

    expected_lms_prefixes = [
        "/api/v1/lms/plants/",
        "/api/v1/lms/plants/{plantId}",
        "/api/v1/lms/plants/{plantId}/departments",
        "/api/v1/lms/departments/",
        "/api/v1/lms/departments/{departmentId}",
        "/api/v1/lms/departments/{departmentId}/sub-departments",
        "/api/v1/lms/sub-departments/",
        "/api/v1/lms/sub-departments/{subDepartmentId}",
        "/api/v1/lms/sub-departments/{subDepartmentId}/lines",
        "/api/v1/lms/lines/",
        "/api/v1/lms/lines/{lineId}",
        "/api/v1/lms/lines/{lineId}/machines",
        "/api/v1/lms/machines/",
        "/api/v1/lms/machines/{machineId}",
    ]

    print("\n[1] Checking OpenAPI Route Registration...")
    for ep in expected_lms_prefixes:
        assert ep in paths, f"Missing endpoint in OpenAPI schema: {ep}"
        print(f"  [OK] Found: {ep}")

    # Verify no legacy un-namespaced routes remain
    for p in paths.keys():
        if p != "/":
            assert (
                p.startswith("/api/v1/lms")
                or p.startswith("/api/v1/dashboard")
                or p.startswith("/api/v1/cms")
                or p.startswith("/api/v1/auth")
                or p.startswith("/api/auth")
                or p.startswith("/api/lms")
            ), f"Non-modular route found: {p}"
    print("  [OK] All routes are correctly namespaced!")

    # 2. Database Model & Relationship Testing
    print("\n[2] Testing Database Models with In-Memory SQLite...")
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)
    db = TestSession()
    print("  [OK] All 5 LMS tables compiled and created successfully.")

    # 3. Test Plant CRUD
    print("\n[3] Testing Plant Service CRUD...")
    p1 = plantsService.createPlant(db, PlantCreate(plantName="Gurugram Plant"))
    assert p1.id == 1
    assert p1.plantName == "Gurugram Plant"

    p2 = plantsService.createPlant(db, PlantCreate(plantName="Pune Plant"))
    assert p2.id == 2

    all_plants = plantsService.getAllPlants(db)
    assert len(all_plants) == 2

    updated_p = plantsService.updatePlant(db, 1, PlantUpdate(plantName="Gurugram Central Plant"))
    assert updated_p.plantName == "Gurugram Central Plant"
    print("  [OK] Plant CRUD operations verified.")

    # 4. Test Department CRUD & Hierarchy Validation
    print("\n[4] Testing Department Service CRUD & Hierarchy...")
    try:
        departmentsService.createDepartment(db, DepartmentCreate(plantId=999, departmentName="Invalid"))
        assert False, "Should have failed with 404 for invalid plantId"
    except HTTPException as e:
        assert e.status_code == 404

    d1 = departmentsService.createDepartment(db, DepartmentCreate(plantId=1, departmentName="Body Shop"))
    assert d1.id == 1
    assert d1.plantId == 1

    d2 = departmentsService.createDepartment(db, DepartmentCreate(plantId=1, departmentName="Paint Shop"))
    d3 = departmentsService.createDepartment(db, DepartmentCreate(plantId=2, departmentName="Assembly"))

    p1_depts = departmentsService.getAllDepartments(db, plantId=1)
    assert len(p1_depts) == 2
    p2_depts = departmentsService.getAllDepartments(db, plantId=2)
    assert len(p2_depts) == 1
    print("  [OK] Department CRUD and plantId hierarchy verified.")

    # 5. Test SubDepartment CRUD & Hierarchy
    print("\n[5] Testing SubDepartment Service CRUD & Hierarchy...")
    sd1 = subDepartmentsService.createSubDepartment(
        db, SubDepartmentCreate(departmentId=1, subDepartmentName="Welding Section")
    )
    assert sd1.plantId == 1  # auto-inferred
    assert sd1.departmentId == 1

    sd2 = subDepartmentsService.createSubDepartment(
        db, SubDepartmentCreate(plantId=1, departmentId=1, subDepartmentName="Stamping Section")
    )
    assert sd2.plantId == 1

    # Hierarchy mismatch check
    try:
        subDepartmentsService.createSubDepartment(
            db, SubDepartmentCreate(plantId=2, departmentId=1, subDepartmentName="Mismatch")
        )
        assert False, "Should have failed with 400 for hierarchy mismatch"
    except HTTPException as e:
        assert e.status_code == 400
    print("  [OK] SubDepartment CRUD and hierarchy integrity verified.")

    # 6. Test Line CRUD & Hierarchy
    print("\n[6] Testing Line Service CRUD & Hierarchy...")
    l1 = linesService.createLine(db, LineCreate(subDepartmentId=1, lineName="Welding Line 1"))
    assert l1.subDepartmentId == 1
    assert l1.departmentId == 1
    assert l1.plantId == 1

    l2 = linesService.createLine(
        db, LineCreate(plantId=1, departmentId=1, subDepartmentId=1, lineName="Welding Line 2")
    )
    assert l2.plantId == 1

    try:
        linesService.createLine(
            db, LineCreate(plantId=2, departmentId=1, subDepartmentId=1, lineName="Mismatch Line")
        )
        assert False, "Should have failed with 400 for mismatch"
    except HTTPException as e:
        assert e.status_code == 400
    print("  [OK] Line CRUD and hierarchy integrity verified.")

    # 7. Test Machine CRUD & Hierarchy
    print("\n[7] Testing Machine Service CRUD & Hierarchy...")
    m1 = machineService.createMachine(db, MachineCreate(lineId=1, machineName="Robotic Welder 01"))
    assert m1.lineId == 1
    assert m1.subDepartmentId == 1
    assert m1.departmentId == 1
    assert m1.plantId == 1

    m2 = machineService.createMachine(
        db, MachineCreate(plantId=1, departmentId=1, subDepartmentId=1, lineId=1, machineName="Robotic Welder 02")
    )
    assert m2.plantId == 1

    try:
        machineService.createMachine(
            db, MachineCreate(plantId=2, lineId=1, machineName="Mismatch Machine")
        )
        assert False, "Should have failed with 400 for mismatch"
    except HTTPException as e:
        assert e.status_code == 400
    print("  [OK] Machine CRUD and hierarchy integrity verified.")

    # 8. Test Cascade Deletion Protection
    print("\n[8] Testing Cascade Deletion Protection...")
    try:
        plantsService.deletePlant(db, 1)
        assert False, "Plant delete should be blocked when departments exist"
    except HTTPException as e:
        assert e.status_code == 400

    try:
        departmentsService.deleteDepartment(db, 1)
        assert False, "Department delete should be blocked when sub-departments exist"
    except HTTPException as e:
        assert e.status_code == 400

    try:
        subDepartmentsService.deleteSubDepartment(db, 1)
        assert False, "SubDepartment delete should be blocked when lines exist"
    except HTTPException as e:
        assert e.status_code == 400

    try:
        linesService.deleteLine(db, 1)
        assert False, "Line delete should be blocked when machines exist"
    except HTTPException as e:
        assert e.status_code == 400

    # Clean bottom-up deletion
    machineService.deleteMachine(db, m1.id)
    machineService.deleteMachine(db, m2.id)
    linesService.deleteLine(db, l1.id)
    linesService.deleteLine(db, l2.id)
    subDepartmentsService.deleteSubDepartment(db, sd1.id)
    subDepartmentsService.deleteSubDepartment(db, sd2.id)
    departmentsService.deleteDepartment(db, d1.id)
    departmentsService.deleteDepartment(db, d2.id)
    plantsService.deletePlant(db, 1)

    assert plantsService.getPlantById(db, 1) is None
    print("  [OK] Cascading deletion protection and clean deletion verified.")

    print("\n==================================================")
    print("  ALL MODULAR ARCHITECTURE TESTS PASSED (100%)    ")
    print("==================================================")

if __name__ == "__main__":
    run_all_tests()
