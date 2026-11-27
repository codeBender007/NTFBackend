"""NTF LMS users service.

Handles manual User CRUD and Excel/CSV bulk employee import with
database-backed hierarchy matching for Plant, Department, SubDepartment,
Line, and Machine foreign keys.
"""
from __future__ import annotations

import io
import logging
import math
import re
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.LMS.models.departmentsModel import Department
from app.LMS.models.linesModel import Line
from app.LMS.models.machineModel import Machine
from app.LMS.models.plantsModel import Plant
from app.LMS.models.subDepartmentsModel import SubDepartment
from app.LMS.models.userModel import User
from app.LMS.schemas.userSchema import UserCreate, UserUpdate
from app.core.security import get_password_hash

# Canonical Excel header -> User model column.
EXCEL_FIELDS = {
    'SNo.': 'sno', 'Paycode': 'payCode', 'CardNo': 'cardNo',
    'EmployeeName': 'empName', 'Date_Of_Birth': 'dob',
    'Date_Of_Join': 'dateOfJoining', 'LeavingDate': 'leavingDate',
    'Company': 'companyName', 'Department': 'departmentName',
    'SubDepartment': 'subDepartmentName', 'Line': 'lineName',
    'Machine': 'machineName',
    'Shift': 'shift', 'Category': 'category', 'Grade': 'grade',
    'Designation': 'designation', 'Sex': 'gender',
    'Blood_Group': 'bloodGroup', 'Bank_Acc': 'bankAccount',
    'Father_Name': 'fatherName', 'Marital_Status': 'maritalStatus',
    'Email': 'email', 'Mobile_No': 'mobileNo', 'PF_No': 'pfNo',
    'ESI_No': 'esiNo', 'Pan_No': 'panNo', 'Adhar_No': 'aadharNo',
    'First_Of_Day': 'firstOfDay', 'Address_1': 'address',
    'isDojo': 'isDojo', 'Skil  Level': 'skillLevel', 'Active': 'active',
    'Basic': 'salary', 'HRA': 'hra',
}

# Flexible case/spacing/punctuation-insensitive header aliases -> canonical header name.
HEADER_ALIASES = {
    'sno': 'SNo.',
    'paycode': 'Paycode',
    'cardno': 'CardNo',
    'employeename': 'EmployeeName',
    'empname': 'EmployeeName',
    'dateofbirth': 'Date_Of_Birth',
    'dob': 'Date_Of_Birth',
    'dateofjoin': 'Date_Of_Join',
    'dateofjoining': 'Date_Of_Join',
    'joiningdate': 'Date_Of_Join',
    'leavingdate': 'LeavingDate',
    'company': 'Company',
    'companyname': 'Company',
    'plant': 'Plant',
    'plantname': 'Plant',
    'plantlocation': 'Plant',
    'department': 'Department',
    'departmentname': 'Department',
    'dept': 'Department',
    'deptname': 'Department',
    'subdepartment': 'SubDepartment',
    'subdepartmentname': 'SubDepartment',
    'subdept': 'SubDepartment',
    'subdeptname': 'SubDepartment',
    'line': 'Line',
    'linename': 'Line',
    'machine': 'Machine',
    'machinename': 'Machine',
    'shift': 'Shift',
    'category': 'Category',
    'grade': 'Grade',
    'designation': 'Designation',
    'sex': 'Sex',
    'gender': 'Sex',
    'bloodgroup': 'Blood_Group',
    'bankacc': 'Bank_Acc',
    'bankaccount': 'Bank_Acc',
    'fathername': 'Father_Name',
    'maritalstatus': 'Marital_Status',
    'email': 'Email',
    'mobileno': 'Mobile_No',
    'pfno': 'PF_No',
    'esino': 'ESI_No',
    'panno': 'Pan_No',
    'adharno': 'Adhar_No',
    'aadharno': 'Adhar_No',
    'firstofday': 'First_Of_Day',
    'address1': 'Address_1',
    'address2': 'Address_2',
    'isdojo': 'isDojo',
    'skillevel': 'Skil  Level',
    'skilllevel': 'Skil  Level',
    'active': 'Active',
    'basic': 'Basic',
    'salary': 'Basic',
    'hra': 'HRA',
}

# Known spelling typo aliases applied as fallback during hierarchy name lookup
# (e.g. Excel has DISPACTH / DISPACTHSubDep / DISPACTHLine / DISPACTHMachine while DB has DISPATCH*).
NAME_TYPO_ALIASES = {
    'DISPACTH': 'DISPATCH',
}

USER_COLS = set(User.__table__.columns.keys())
DEFAULT_IMPORT_PASSWORD = 'Welcome@123'
RESET_EXISTING_PASSWORDS_ON_UPLOAD = False  # Existing passwords must NOT change during re-upload.
logger = logging.getLogger(__name__)
BATCH_SIZE = 500
USER_EDIT_COLS = USER_COLS - {'id', 'passwordHash', 'createdAt', 'updatedAt'}

_AMBIGUOUS = object()


def _model_dict(schema, *, exclude_unset=False):
    """Works with Pydantic 1 and 2."""
    if hasattr(schema, 'model_dump'):
        return schema.model_dump(exclude_unset=exclude_unset)
    return schema.dict(exclude_unset=exclude_unset)


EXCEL_ERROR_TOKENS = {'#N/A', '#REF!', '#VALUE!', '#DIV/0!', '#NAME?', '#NUM!', '#NULL!'}


def _blank(value):
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped.upper() in EXCEL_ERROR_TOKENS
    if isinstance(value, float):
        return math.isnan(value)
    if isinstance(value, (int, bool, date, datetime, Decimal)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _string(value):
    if _blank(value):
        return None
    v = str(value).strip()
    if re.fullmatch(r'\d+\.0', v):
        v = v[:-2]
    return v or None


def _integer(value):
    if _blank(value):
        return None
    cleaned = Decimal(str(value).strip())
    return int(cleaned) if cleaned % 1 == 0 else _invalid('integer', value)


def _invalid(label, value):
    raise ValueError(f'Invalid {label}: {value!r}')


def _date(value):
    if _blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    # Excel report dates are DD/MM/YYYY. Also allow ISO YYYY-MM-DD and DD-MM-YYYY.
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    _invalid('date (expected DD/MM/YYYY)', value)


def _money(value, field):
    """Validate decimal pay amounts, preserving two-decimal precision."""
    if _blank(value):
        return None
    try:
        cleaned = str(value).strip().replace(',', '')
        amount = Decimal(cleaned)
        if not amount.is_finite() or amount < 0 or amount > Decimal('9999999999999999.99'):
            raise ValueError('outside allowed DECIMAL(18,2) range')
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, InvalidOperation) as exc:
        raise ValueError(f'Invalid {field} amount: {value!r}') from exc


def _dob_password(dob):
    """Default password exactly DDMMYYYY, e.g. 01/01/1980 -> 01011980."""
    if dob is None:
        raise ValueError('Date_Of_Birth is required for DOB-based default password')
    return dob.strftime('%d%m%Y')


def _boolean(value, field):
    if _blank(value):
        return None
    if isinstance(value, bool):
        return value
    value = str(value).strip().upper()
    if value in ('Y', 'YES', 'TRUE', '1'):
        return True
    if value in ('N', 'NO', 'FALSE', '0'):
        return False
    _invalid(field, value)


def _normalize_header(col_name: str) -> str:
    """Map an Excel column header to its canonical name if known."""
    trimmed = str(col_name).strip()
    if trimmed in EXCEL_FIELDS or trimmed in ('Address_2', 'Plant'):
        return trimmed
    compact = re.sub(r'[\s_\-\.]+', '', trimmed.lower())
    return HEADER_ALIASES.get(compact, trimmed)


def _normalize_name(value) -> Optional[str]:
    """Case-insensitive, whitespace-trimmed and collapsed normalization for hierarchy names."""
    text = _string(value)
    if not text:
        return None
    return re.sub(r'\s+', ' ', text).strip().upper()


def _compact_name(norm_name: Optional[str]) -> Optional[str]:
    """Strip spaces/underscores/hyphens for secondary matching on minor spacing variations."""
    if not norm_name:
        return None
    return re.sub(r'[\s_\-]+', '', norm_name) or None


def _alias_variants(norm_name: str) -> List[str]:
    variants = [norm_name]
    for wrong, right in NAME_TYPO_ALIASES.items():
        if wrong in norm_name:
            fixed = norm_name.replace(wrong, right)
            if fixed not in variants:
                variants.append(fixed)
    return variants


def _put_unique(mapping: dict, key, record) -> None:
    existing = mapping.get(key)
    if existing is None:
        mapping[key] = record
    elif existing is not _AMBIGUOUS and existing.id != record.id:
        mapping[key] = _AMBIGUOUS


class _HierarchyLookup:
    """In-memory, case/whitespace-insensitive lookup tables for Plant -> Department -> SubDepartment -> Line -> Machine."""

    def __init__(self, db: Session):
        self.plants_by_id: Dict[int, Plant] = {}
        self.plants_by_name: dict = {}
        self.plants_by_compact: dict = {}

        self.depts_by_id: Dict[int, Department] = {}
        self.depts_by_plant_name: dict = {}
        self.depts_by_plant_compact: dict = {}
        self.depts_by_name: dict = {}
        self.depts_by_compact: dict = {}
        self.dept_ids_by_name: Dict[str, List[int]] = {}
        self.dept_ids_by_compact: Dict[str, List[int]] = {}

        self.subdepts_by_id: Dict[int, SubDepartment] = {}
        self.subdepts_by_dept_name: dict = {}
        self.subdepts_by_dept_compact: dict = {}
        self.subdepts_by_name: dict = {}
        self.subdepts_by_compact: dict = {}

        self.lines_by_id: Dict[int, Line] = {}
        self.lines_by_subdept_name: dict = {}
        self.lines_by_subdept_compact: dict = {}
        self.lines_by_dept_name: dict = {}
        self.lines_by_dept_compact: dict = {}
        self.lines_by_name: dict = {}
        self.lines_by_compact: dict = {}

        self.machines_by_id: Dict[int, Machine] = {}
        self.machines_by_line_name: dict = {}
        self.machines_by_line_compact: dict = {}
        self.machines_by_subdept_name: dict = {}
        self.machines_by_subdept_compact: dict = {}
        self.machines_by_dept_name: dict = {}
        self.machines_by_dept_compact: dict = {}
        self.machines_by_name: dict = {}
        self.machines_by_compact: dict = {}

        self._load(db)

    def _load(self, db: Session) -> None:
        for plant in db.query(Plant).all():
            self.plants_by_id[int(plant.id)] = plant
            norm = _normalize_name(plant.plantName)
            if norm:
                _put_unique(self.plants_by_name, norm, plant)
                _put_unique(self.plants_by_compact, _compact_name(norm), plant)

        for dept in db.query(Department).all():
            dept_id = int(dept.id)
            plant_id = int(dept.plantId) if dept.plantId is not None else None
            self.depts_by_id[dept_id] = dept
            norm = _normalize_name(dept.departmentName)
            if norm:
                compact = _compact_name(norm)
                _put_unique(self.depts_by_name, norm, dept)
                _put_unique(self.depts_by_compact, compact, dept)
                self.dept_ids_by_name.setdefault(norm, []).append(dept_id)
                if compact:
                    self.dept_ids_by_compact.setdefault(compact, []).append(dept_id)
                if plant_id is not None:
                    _put_unique(self.depts_by_plant_name, (plant_id, norm), dept)
                    _put_unique(self.depts_by_plant_compact, (plant_id, compact), dept)

        for sub in db.query(SubDepartment).all():
            sub_id = int(sub.id)
            dept_id = int(sub.departmentId) if sub.departmentId is not None else None
            self.subdepts_by_id[sub_id] = sub
            norm = _normalize_name(sub.subDepartmentName)
            if norm:
                compact = _compact_name(norm)
                _put_unique(self.subdepts_by_name, norm, sub)
                _put_unique(self.subdepts_by_compact, compact, sub)
                if dept_id is not None:
                    _put_unique(self.subdepts_by_dept_name, (dept_id, norm), sub)
                    _put_unique(self.subdepts_by_dept_compact, (dept_id, compact), sub)

        for line in db.query(Line).all():
            line_id = int(line.id)
            sub_id = int(line.subDepartmentId) if line.subDepartmentId is not None else None
            dept_id = int(line.departmentId) if line.departmentId is not None else None
            self.lines_by_id[line_id] = line
            norm = _normalize_name(line.lineName)
            if norm:
                compact = _compact_name(norm)
                _put_unique(self.lines_by_name, norm, line)
                _put_unique(self.lines_by_compact, compact, line)
                if sub_id is not None:
                    _put_unique(self.lines_by_subdept_name, (sub_id, norm), line)
                    _put_unique(self.lines_by_subdept_compact, (sub_id, compact), line)
                if dept_id is not None:
                    _put_unique(self.lines_by_dept_name, (dept_id, norm), line)
                    _put_unique(self.lines_by_dept_compact, (dept_id, compact), line)

        for machine in db.query(Machine).all():
            mach_id = int(machine.id)
            line_id = int(machine.lineId) if machine.lineId is not None else None
            sub_id = int(machine.subDepartmentId) if machine.subDepartmentId is not None else None
            dept_id = int(machine.departmentId) if machine.departmentId is not None else None
            self.machines_by_id[mach_id] = machine
            norm = _normalize_name(machine.machineName)
            if norm:
                compact = _compact_name(norm)
                _put_unique(self.machines_by_name, norm, machine)
                _put_unique(self.machines_by_compact, compact, machine)
                if line_id is not None:
                    _put_unique(self.machines_by_line_name, (line_id, norm), machine)
                    _put_unique(self.machines_by_line_compact, (line_id, compact), machine)
                if sub_id is not None:
                    _put_unique(self.machines_by_subdept_name, (sub_id, norm), machine)
                    _put_unique(self.machines_by_subdept_compact, (sub_id, compact), machine)
                if dept_id is not None:
                    _put_unique(self.machines_by_dept_name, (dept_id, norm), machine)
                    _put_unique(self.machines_by_dept_compact, (dept_id, compact), machine)

    @staticmethod
    def _lookup(raw_value, exact_map: dict, compact_map: dict, scope_id: Optional[int] = None) -> Tuple[Optional[object], bool]:
        norm = _normalize_name(raw_value)
        if not norm:
            return None, False

        saw_ambiguous = False
        variants = _alias_variants(norm)

        for candidate in variants:
            key = (scope_id, candidate) if scope_id is not None else candidate
            if key in exact_map:
                hit = exact_map[key]
                if hit is _AMBIGUOUS:
                    saw_ambiguous = True
                else:
                    return hit, False

        for candidate in variants:
            compact = _compact_name(candidate)
            if not compact:
                continue
            key = (scope_id, compact) if scope_id is not None else compact
            if key in compact_map:
                hit = compact_map[key]
                if hit is _AMBIGUOUS:
                    saw_ambiguous = True
                else:
                    return hit, False

        return None, saw_ambiguous

    def _candidate_dept_ids(self, raw_dept) -> List[int]:
        norm = _normalize_name(raw_dept)
        if not norm:
            return []
        ids: List[int] = []
        for candidate in _alias_variants(norm):
            for dept_id in self.dept_ids_by_name.get(candidate, []):
                if dept_id not in ids:
                    ids.append(dept_id)
            compact = _compact_name(candidate)
            if compact:
                for dept_id in self.dept_ids_by_compact.get(compact, []):
                    if dept_id not in ids:
                        ids.append(dept_id)
        return ids

    def resolve(
        self,
        raw_plant,
        raw_dept,
        raw_subdept,
        raw_line,
        raw_machine,
    ) -> Tuple[dict, List[str]]:
        """Resolve hierarchy names to exact DB foreign key IDs without failing on unmatched/missing fields."""
        warnings: List[str] = []

        plant_id: Optional[int] = None
        dept_obj: Optional[Department] = None
        sub_obj: Optional[SubDepartment] = None
        line_obj: Optional[Line] = None
        machine_obj: Optional[Machine] = None

        # 0. Optional Plant match
        if not _blank(raw_plant):
            plant_obj, _ = self._lookup(raw_plant, self.plants_by_name, self.plants_by_compact)
            if plant_obj is not None:
                plant_id = int(plant_obj.id)

        # 1. Department match
        dept_ambiguous = False
        if not _blank(raw_dept):
            if plant_id is not None:
                dept_obj, dept_ambiguous = self._lookup(
                    raw_dept, self.depts_by_plant_name, self.depts_by_plant_compact, scope_id=plant_id
                )
            if dept_obj is None:
                dept_obj, dept_ambiguous = self._lookup(raw_dept, self.depts_by_name, self.depts_by_compact)

        # 2. SubDepartment match (scoped to matched department when available)
        sub_ambiguous = False
        if not _blank(raw_subdept):
            if dept_obj is not None:
                sub_obj, sub_ambiguous = self._lookup(
                    raw_subdept,
                    self.subdepts_by_dept_name,
                    self.subdepts_by_dept_compact,
                    scope_id=int(dept_obj.id),
                )
            else:
                # If department was ambiguous across plants, try disambiguating via subDepartment
                if dept_ambiguous and not _blank(raw_dept):
                    matches = []
                    for cand_dept_id in self._candidate_dept_ids(raw_dept):
                        cand_sub, _ = self._lookup(
                            raw_subdept,
                            self.subdepts_by_dept_name,
                            self.subdepts_by_dept_compact,
                            scope_id=cand_dept_id,
                        )
                        if cand_sub is not None:
                            matches.append((cand_dept_id, cand_sub))
                    if len(matches) == 1:
                        dept_obj = self.depts_by_id.get(matches[0][0])
                        sub_obj = matches[0][1]
                        dept_ambiguous = False
                if sub_obj is None:
                    sub_obj, sub_ambiguous = self._lookup(
                        raw_subdept, self.subdepts_by_name, self.subdepts_by_compact
                    )
                    if sub_obj is not None and dept_obj is None and _blank(raw_dept):
                        dept_obj = self.depts_by_id.get(int(sub_obj.departmentId))

        # 3. Line match (scoped to subDepartment -> department -> global)
        line_ambiguous = False
        if not _blank(raw_line):
            if sub_obj is not None:
                line_obj, line_ambiguous = self._lookup(
                    raw_line,
                    self.lines_by_subdept_name,
                    self.lines_by_subdept_compact,
                    scope_id=int(sub_obj.id),
                )
            elif dept_obj is not None:
                line_obj, line_ambiguous = self._lookup(
                    raw_line,
                    self.lines_by_dept_name,
                    self.lines_by_dept_compact,
                    scope_id=int(dept_obj.id),
                )
            else:
                line_obj, line_ambiguous = self._lookup(raw_line, self.lines_by_name, self.lines_by_compact)
                if line_obj is not None:
                    if sub_obj is None and _blank(raw_subdept):
                        sub_obj = self.subdepts_by_id.get(int(line_obj.subDepartmentId))
                    if dept_obj is None and _blank(raw_dept):
                        dept_obj = self.depts_by_id.get(int(line_obj.departmentId))

        # 4. Machine match (scoped to line -> subDepartment -> department -> global)
        machine_ambiguous = False
        if not _blank(raw_machine):
            if line_obj is not None:
                machine_obj, machine_ambiguous = self._lookup(
                    raw_machine,
                    self.machines_by_line_name,
                    self.machines_by_line_compact,
                    scope_id=int(line_obj.id),
                )
            elif sub_obj is not None:
                machine_obj, machine_ambiguous = self._lookup(
                    raw_machine,
                    self.machines_by_subdept_name,
                    self.machines_by_subdept_compact,
                    scope_id=int(sub_obj.id),
                )
            elif dept_obj is not None:
                machine_obj, machine_ambiguous = self._lookup(
                    raw_machine,
                    self.machines_by_dept_name,
                    self.machines_by_dept_compact,
                    scope_id=int(dept_obj.id),
                )
            else:
                machine_obj, machine_ambiguous = self._lookup(
                    raw_machine, self.machines_by_name, self.machines_by_compact
                )
                if machine_obj is not None:
                    if line_obj is None and _blank(raw_line):
                        line_obj = self.lines_by_id.get(int(machine_obj.lineId))
                    if sub_obj is None and _blank(raw_subdept):
                        sub_obj = self.subdepts_by_id.get(int(machine_obj.subDepartmentId))
                    if dept_obj is None and _blank(raw_dept):
                        dept_obj = self.depts_by_id.get(int(machine_obj.departmentId))

        # Derive plantId from matched hierarchy record if not already set (or align with matched department)
        for obj in (dept_obj, sub_obj, line_obj, machine_obj):
            if obj is not None and obj.plantId is not None:
                candidate_plant_id = int(obj.plantId)
                if candidate_plant_id in self.plants_by_id:
                    plant_id = candidate_plant_id
                    break

        # Build non-fatal warnings for any provided but unmatched/ambiguous hierarchy values
        if not _blank(raw_dept) and dept_obj is None:
            reason = 'ambiguous across multiple plants' if dept_ambiguous else 'not found in departments'
            warnings.append(f'Department {_string(raw_dept)!r} {reason}; departmentId left NULL')
        if not _blank(raw_subdept) and sub_obj is None:
            reason = 'ambiguous' if sub_ambiguous else 'not found in subDepartments'
            warnings.append(f'SubDepartment {_string(raw_subdept)!r} {reason}; subDepartmentId left NULL')
        if not _blank(raw_line) and line_obj is None:
            reason = 'ambiguous' if line_ambiguous else 'not found in lines'
            warnings.append(f'Line {_string(raw_line)!r} {reason}; lineId left NULL')
        if not _blank(raw_machine) and machine_obj is None:
            reason = 'ambiguous' if machine_ambiguous else 'not found in machines'
            warnings.append(f'Machine {_string(raw_machine)!r} {reason}; machineId left NULL')

        plant_obj = self.plants_by_id.get(plant_id) if plant_id is not None else None

        resolved = {
            'plantId': plant_id,
            'plantLocation': plant_obj.plantName if plant_obj is not None else None,
            'departmentId': int(dept_obj.id) if dept_obj is not None else None,
            'departmentName': dept_obj.departmentName if dept_obj is not None else _string(raw_dept),
            'subDepartmentId': int(sub_obj.id) if sub_obj is not None else None,
            'subDepartmentName': sub_obj.subDepartmentName if sub_obj is not None else _string(raw_subdept),
            'lineId': int(line_obj.id) if line_obj is not None else None,
            'lineName': line_obj.lineName if line_obj is not None else _string(raw_line),
            'machineId': int(machine_obj.id) if machine_obj is not None else None,
            'machineName': machine_obj.machineName if machine_obj is not None else _string(raw_machine),
        }
        return resolved, warnings


def _row_data(row: dict, hierarchy: _HierarchyLookup, present_cols: Set[str]) -> Tuple[dict, List[str]]:
    paycode = _string(row.get('Paycode'))
    if not paycode:
        raise ValueError('Paycode is empty')
    name = _string(row.get('EmployeeName'))
    if not name:
        raise ValueError('EmployeeName is empty')

    data = {}
    for excel_field, model_field in EXCEL_FIELDS.items():
        if model_field not in USER_COLS:
            continue
        if excel_field not in present_cols:
            continue
        # Hierarchy fields are resolved explicitly below.
        if model_field in ('departmentName', 'subDepartmentName', 'lineName', 'machineName'):
            continue
        value = row.get(excel_field)
        if model_field in ('dob', 'dateOfJoining', 'leavingDate'):
            data[model_field] = _date(value)
        elif model_field in ('sno', 'skillLevel'):
            # DB skillLevel is varchar, even though Excel uses 1/2/3/4.
            data[model_field] = (
                _string(_integer(value)) if model_field == 'skillLevel' and not _blank(value)
                else _integer(value)
            )
        elif model_field in ('salary', 'hra'):
            data[model_field] = _money(value, excel_field)
        elif model_field in ('isDojo', 'active'):
            parsed = _boolean(value, excel_field)
            data[model_field] = parsed if parsed is not None else (False if model_field == 'isDojo' else True)
        elif model_field == 'gender':
            raw = _string(value)
            data[model_field] = {'M': 'Male', 'F': 'Female'}.get(raw.upper(), raw) if raw else None
        else:
            data[model_field] = _string(value)

    # Concatenate both Excel address lines, within SQL column limit.
    if 'Address_1' in present_cols or 'Address_2' in present_cols:
        address = ' '.join(filter(None, (_string(row.get('Address_1')), _string(row.get('Address_2')))))
        if address:
            if len(address) > 500:
                raise ValueError('Combined address exceeds 500 characters')
            data['address'] = address
        else:
            data['address'] = None

    data['payCode'] = paycode
    data['empName'] = name

    # Resolve Plant, Department, SubDepartment, Line, and Machine against existing DB records
    resolved_hierarchy, row_warnings = hierarchy.resolve(
        raw_plant=row.get('Plant') if 'Plant' in present_cols else None,
        raw_dept=row.get('Department') if 'Department' in present_cols else None,
        raw_subdept=row.get('SubDepartment') if 'SubDepartment' in present_cols else None,
        raw_line=row.get('Line') if 'Line' in present_cols else None,
        raw_machine=row.get('Machine') if 'Machine' in present_cols else None,
    )

    # Assign resolved hierarchy IDs and names for columns present in the Excel (or inferred via match).
    # Keep uniform keys per batch so SQLAlchemy bulk_insert/bulk_update emits a single executemany.
    if 'Plant' in present_cols or 'Department' in present_cols or resolved_hierarchy['plantId'] is not None:
        if 'plantId' in USER_COLS:
            data['plantId'] = resolved_hierarchy['plantId']
        if 'plantLocation' in USER_COLS:
            data['plantLocation'] = resolved_hierarchy['plantLocation']

    if 'Department' in present_cols or resolved_hierarchy['departmentId'] is not None:
        if 'departmentId' in USER_COLS:
            data['departmentId'] = resolved_hierarchy['departmentId']
        if 'departmentName' in USER_COLS:
            data['departmentName'] = resolved_hierarchy['departmentName']

    if 'SubDepartment' in present_cols or resolved_hierarchy['subDepartmentId'] is not None:
        if 'subDepartmentId' in USER_COLS:
            data['subDepartmentId'] = resolved_hierarchy['subDepartmentId']
        if 'subDepartmentName' in USER_COLS:
            data['subDepartmentName'] = resolved_hierarchy['subDepartmentName']

    if 'Line' in present_cols or resolved_hierarchy['lineId'] is not None:
        if 'lineId' in USER_COLS:
            data['lineId'] = resolved_hierarchy['lineId']
        if 'lineName' in USER_COLS:
            data['lineName'] = resolved_hierarchy['lineName']

    if 'Machine' in present_cols or resolved_hierarchy['machineId'] is not None:
        if 'machineId' in USER_COLS:
            data['machineId'] = resolved_hierarchy['machineId']
        if 'machineName' in USER_COLS:
            data['machineName'] = resolved_hierarchy['machineName']

    # Validate text lengths early so SQL batch won't fail on one oversized cell.
    for col_name, value in data.items():
        if value is not None and col_name in USER_COLS:
            column_type = User.__table__.columns[col_name].type
            max_len = getattr(column_type, 'length', None)
            if max_len and isinstance(value, str) and len(value) > max_len:
                raise ValueError(f'{col_name} exceeds {max_len} characters')

    if data.get('leavingDate') and data.get('dateOfJoining'):
        if data['leavingDate'] < data['dateOfJoining']:
            raise ValueError('LeavingDate cannot be earlier than Date_Of_Join')

    return data, row_warnings


def getAllUsers(db: Session, plantId: Optional[int] = None,
                departmentId: Optional[int] = None, skillLevel: Optional[str] = None,
                active: Optional[bool] = None, skip: int = 0, limit: int = 100,
                subDepartmentId: Optional[int] = None, lineId: Optional[int] = None,
                machineId: Optional[int] = None, shift: Optional[str] = None,
                startDate: Optional[date] = None, endDate: Optional[date] = None):
    if startDate is not None and endDate is not None and startDate > endDate:
        raise HTTPException(400, 'startDate cannot be greater than endDate')
    query = db.query(User)
    for field, value in (
        ('plantId', plantId), ('departmentId', departmentId),
        ('subDepartmentId', subDepartmentId), ('lineId', lineId),
        ('machineId', machineId), ('skillLevel', skillLevel), ('active', active)
    ):
        if value is not None:
            query = query.filter(getattr(User, field) == value)
    if shift is not None and shift.strip():
        query = query.filter(User.shift == shift.strip())
    if startDate is not None:
        query = query.filter(User.dateOfJoining >= startDate)
    if endDate is not None:
        query = query.filter(User.dateOfJoining <= endDate)
    return query.order_by(User.id).offset(max(skip, 0)).limit(min(max(limit, 1), 5000)).all()


def getUserById(db: Session, userId: int):
    return db.query(User).filter(User.id == userId).first()


def getUserByPayCode(db: Session, payCode: str):
    return db.query(User).filter(User.payCode == payCode).first()


def createUser(db: Session, userData: UserCreate):
    values = _model_dict(userData)
    raw_pwd = values.pop('password', None) or 'Welcome@123'
    values.pop('passwordHash', None)
    values = {k: v for k, v in values.items() if k in USER_EDIT_COLS}
    if getUserByPayCode(db, values.get('payCode')):
        raise HTTPException(400, f"User with PayCode {values['payCode']} already exists")
    values['passwordHash'] = get_password_hash(raw_pwd)
    user = User(**values)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(400, 'Invalid user data, duplicate payCode or hierarchy reference') from e
    return user


def updateUser(db: Session, userId: int, updateData: UserUpdate):
    user = getUserById(db, userId)
    if user is None:
        return None

    values = _model_dict(updateData, exclude_unset=True)

    password = values.pop('password', None)
    values.pop('passwordHash', None)

    for field, val in values.items():
        if field in USER_EDIT_COLS:
            setattr(user, field, val)

    if password:
        user.passwordHash = get_password_hash(password)

    try:
        db.commit()
        db.refresh(user)

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            400,
            'Invalid update: duplicate payCode or hierarchy reference'
        ) from e

    return user


def deleteUser(db: Session, userId: int):
    """Soft delete preserves attendance, skill and training history."""
    user = getUserById(db, userId)
    if user is None:
        return None
    user.active = False
    db.commit()
    db.refresh(user)
    return user


async def processExcelUpload(db: Session, file: UploadFile):
    """Import Excel/CSV with validation, full hierarchy ID matching, and batched SQL writes.

    - Existing payCode: update mapped fields, PRESERVE password/role/roleId.
    - New payCode: hash DOB (DDMMYYYY), create OPERATOR.
    - Matches Department, SubDepartment, Line, and Machine names (case/whitespace-insensitive)
      against existing DB records and saves exact foreign key IDs (departmentId, subDepartmentId,
      lineId, machineId, plus plantId).
    - Missing or unmatched hierarchy values are handled gracefully (ID left NULL) without breaking valid rows.
    - All successfully validated rows are committed in one transaction.
    """
    start = time.perf_counter()
    filename = (file.filename or '').lower()
    if not filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(400, 'Only .xlsx, .xls and .csv are supported')
    contents = await file.read()
    if not contents:
        raise HTTPException(400, 'Uploaded file is empty')
    if len(contents) > 15 * 1024 * 1024:
        raise HTTPException(413, 'Maximum Excel file size is 15 MB')
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents), dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(io.BytesIO(contents), sheet_name=0, dtype=object)
    except Exception as exc:
        raise HTTPException(400, 'Invalid or unreadable Excel/CSV file') from exc

    # Normalize column headers (trim spaces and canonicalize common variants like Sub_Department -> SubDepartment).
    raw_headers = [str(c).strip() for c in df.columns]
    if len(set(raw_headers)) != len(raw_headers):
        raise HTTPException(400, 'Duplicate column names after trimming spaces')

    canonical_headers = [_normalize_header(c) for c in raw_headers]
    if len(set(canonical_headers)) != len(canonical_headers):
        raise HTTPException(400, 'Duplicate column names after header normalization')

    df.columns = canonical_headers
    present_cols = set(canonical_headers)

    missing = {'Paycode', 'EmployeeName'} - present_cols
    if missing:
        raise HTTPException(400, f'Missing Excel columns: {sorted(missing)}')

    required_orm = {
        'salary', 'hra', 'dob', 'passwordHash',
        'plantId', 'departmentId', 'departmentName',
        'subDepartmentId', 'subDepartmentName',
        'lineId', 'lineName',
        'machineId', 'machineName',
    }
    missing_orm = required_orm - USER_COLS
    if missing_orm:
        raise HTTPException(500, f'User model missing columns: {sorted(missing_orm)}')

    try:
        hierarchy = _HierarchyLookup(db)
        ignored = [c for c in canonical_headers if c not in EXCEL_FIELDS and c not in ('Address_2', 'Plant')]
        errors: List[str] = []
        warnings: List[str] = []
        skipped = 0
        seen: Set[str] = set()
        rows: List[Tuple[int, dict]] = []
        match_counts = {
            'plantId': 0,
            'departmentId': 0,
            'subDepartmentId': 0,
            'lineId': 0,
            'machineId': 0,
        }

        for idx, values in enumerate(df.to_dict(orient='records'), start=2):
            if all(_blank(v) for v in values.values()):
                skipped += 1
                continue
            try:
                data, row_warnings = _row_data(values, hierarchy, present_cols)
                pay_code = data['payCode']
                if pay_code in seen:
                    raise ValueError(f'Duplicate Paycode in Excel: {pay_code}')
                seen.add(pay_code)
                for w in row_warnings:
                    warnings.append(f'Excel row {idx} (Paycode {pay_code}): {w}')
                rows.append((idx, data))
            except (ValueError, TypeError, OverflowError, InvalidOperation) as exc:
                skipped += 1
                errors.append(f'Excel row {idx}: {exc}')

        logger.info(
            'Excel import parsed: %s valid, %s invalid, %s warnings in %.2fs',
            len(rows), skipped, len(warnings), time.perf_counter() - start
        )
        if not rows:
            return {
                'totalRows': len(df), 'inserted': 0, 'updated': 0,
                'skipped': skipped, 'errors': errors, 'errorCount': len(errors),
                'warnings': warnings, 'warningCount': len(warnings),
                'durationSeconds': round(time.perf_counter() - start, 2),
                'ignoredExcelColumns': ignored,
                'hierarchyMatches': match_counts,
            }

        # Fetch ONLY id/payCode rather than loading every user + all columns.
        # SQL Server limits SQL IN parameters; split lookups into chunks.
        existing = {}
        codes = [data['payCode'] for _, data in rows]
        for start_idx in range(0, len(codes), BATCH_SIZE):
            part = codes[start_idx:start_idx + BATCH_SIZE]
            existing.update(
                db.query(User.payCode, User.id).filter(User.payCode.in_(part)).all()
            )

        # Hash default password ONCE outside the row loop (avoids hundreds of slow bcrypt calls).
        has_new_users = any(data['payCode'] not in existing for _, data in rows)
        default_password_hash = get_password_hash(DEFAULT_IMPORT_PASSWORD) if has_new_users else None

        inserts, updates = [], []
        for idx, data in rows:
            code = data['payCode']
            if code in existing:
                # Keep passwords, roles, roleId, IDs, createdAt unchanged on Excel update.
                # Explicitly ensure active=True so previously soft-deleted/inactive records
                # reappear in active listings after re-import.
                updated_row = {'id': existing[code], **data, 'active': True}
                updates.append(updated_row)
                saved_row = updated_row
            else:
                saved_row = {
                    **data,
                    'passwordHash': default_password_hash,
                    'role': 'OPERATOR',
                    'active': True if data.get('active') is None else data.get('active'),
                }
                inserts.append(saved_row)

            for key in match_counts:
                if saved_row.get(key) is not None:
                    match_counts[key] += 1

        # SQLAlchemy bulk APIs avoid one ORM flush / SAVEPOINT per employee.
        # BATCH_SIZE prevents oversized parameter payloads to MSSQL while keeping a single commit.
        for offset in range(0, len(updates), BATCH_SIZE):
            db.bulk_update_mappings(User, updates[offset:offset + BATCH_SIZE])
        for offset in range(0, len(inserts), BATCH_SIZE):
            db.bulk_insert_mappings(User, inserts[offset:offset + BATCH_SIZE])
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except (ValueError, TypeError, InvalidOperation) as exc:
        db.rollback()
        logger.warning('Excel import validation error: %s', exc)
        raise HTTPException(400, f'Excel import failed: {exc}') from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Excel import failed; transaction rolled back')
        raise HTTPException(
            500, 'Excel import failed during database save; changes rolled back. See server log.'
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception('Excel import unexpectedly failed')
        raise HTTPException(
            500, f'Excel import failed unexpectedly: {exc}'
        ) from exc

    elapsed = round(time.perf_counter() - start, 2)
    logger.info(
        'Excel import complete: inserted=%s updated=%s skipped=%s matches=%s time=%.2fs',
        len(inserts), len(updates), skipped, match_counts, elapsed
    )
    return {
        'totalRows': len(df),
        'inserted': len(inserts),
        'updated': len(updates),
        'skipped': skipped,
        'errors': errors,
        'errorCount': len(errors),
        'warnings': warnings,
        'warningCount': len(warnings),
        'durationSeconds': elapsed,
        'ignoredExcelColumns': ignored,
        'hierarchyMatches': match_counts,
        'departmentAssignment': (
            'departmentId, subDepartmentId, lineId, machineId, and plantId matched against database records'
        ),
        'passwordPolicy': 'New users default hashed once (Welcome@123 / DOB login); existing passwords preserved',
        'payMapping': 'Basic to salary, HRA to hra',
    }
    