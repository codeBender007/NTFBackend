"""NTF LMS users service. Tested against EmployeeMaster.xlsx column layout.

Replace app/LMS/services/userService.py (adjust filename if your module differs).
Requires pandas, openpyxl, SQLAlchemy, FastAPI and the existing User model/schemas.
"""
from __future__ import annotations

import io
import logging
import time
import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.LMS.models.userModel import User
from app.LMS.schemas.userSchema import UserCreate, UserUpdate
from app.core.security import get_password_hash

# Normalized Excel header -> model column; ONLY columns that have a clear equivalent.
EXCEL_FIELDS = {
    'SNo.': 'sno', 'Paycode': 'payCode', 'CardNo': 'cardNo',
    'EmployeeName': 'empName', 'Date_Of_Birth': 'dob',
    'Date_Of_Join': 'dateOfJoining', 'LeavingDate': 'leavingDate',
    'Company': 'companyName', 'Department': 'departmentName',
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

# Actual Excel typo; approved department master has DISPATCH.
DEPARTMENT_ALIASES = {'DISPACTH': 'DISPATCH'}
APPROVED_DEPARTMENTS = {
    'ACCESSORIES', 'ACCOUNTS', 'ADMIN', 'DISPATCH', 'IT', 'LB',
    'MAINTENANCE', 'NBD', 'OPERATIONS', 'PAINT SHOP', 'PIM',
    'QUALITY', 'STORE', 'TCM', 'TOOL ROOM', 'YED LINE',
}

# These fields intentionally remain NULL for bulk-imported employees.
CLEAR_HIERARCHY_FIELDS = (
    'plantLocation', 'subDepartmentId', 'subDepartmentName',
    'lineId', 'lineName', 'machineId', 'machineName',
)
USER_COLS = set(User.__table__.columns.keys())
RESET_EXISTING_PASSWORDS_ON_UPLOAD = False  # Existing passwords must NOT change during re-upload.
logger = logging.getLogger(__name__)
BATCH_SIZE = 200
USER_EDIT_COLS = USER_COLS - {'id', 'passwordHash', 'createdAt', 'updatedAt'}


def _model_dict(schema, *, exclude_unset=False):
    """Works with Pydantic 1 and 2."""
    if hasattr(schema, 'model_dump'):
        return schema.model_dump(exclude_unset=exclude_unset)
    return schema.dict(exclude_unset=exclude_unset)


def _blank(value):
    if value is None:
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(value, str) and not value.strip()


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
    return int(Decimal(str(value).strip())) if Decimal(str(value).strip()) % 1 == 0 else _invalid('integer', value)


def _invalid(label, value):
    raise ValueError(f'Invalid {label}: {value!r}')


def _date(value):
    if _blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # Excel report dates are DD/MM/YYYY. Do not guess US dates.
    parsed = pd.to_datetime(value, format='%d/%m/%Y', errors='coerce')
    if pd.isna(parsed):
        _invalid('date (expected DD/MM/YYYY)', value)
    return parsed.date()


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


def _department(value):
    name = re.sub(r'\s+', ' ', _string(value).upper()) if _string(value) else None
    return DEPARTMENT_ALIASES.get(name, name)


def _read_departments(db: Session):
    """Map department name -> (department id, plant id) from dbo.departments.

    Never infer plant from department ID. Reject ambiguous department names
    that belong to multiple plants because Excel contains no plant identifier.
    """
    from sqlalchemy import MetaData, Table

    bind = db.get_bind()
    table = Table('departments', MetaData(), autoload_with=bind, schema='dbo')
    columns = {name.lower(): name for name in table.c.keys()}
    name_key = next((columns[x] for x in ('departmentname', 'name', 'department_name') if x in columns), None)
    plant_key = columns.get('plantid') or columns.get('plant_id')
    id_key = columns.get('id')
    if not (name_key and plant_key and id_key):
        raise HTTPException(500, 'dbo.departments requires id, departmentName/name, and plantId columns')

    # Validate plant references before trying to update user rows.
    plant_table = Table('plants', MetaData(), autoload_with=bind, schema='dbo')
    valid_plants = set(db.execute(select(plant_table.c.id)).scalars().all())
    if not valid_plants:
        raise HTTPException(500, 'No plants found in dbo.plants')

    result = {}
    ambiguous = set()
    for dept_id, dept_name, plant_id in db.execute(
        select(table.c[id_key], table.c[name_key], table.c[plant_key])
    ):
        key = _department(dept_name)
        if not key:
            continue
        if plant_id is None or plant_id not in valid_plants:
            raise HTTPException(500, f'Department {key} (ID {dept_id}) lacks a valid plantId')
        candidate = (int(dept_id), int(plant_id))
        if key in result and result[key] != candidate:
            ambiguous.add(key)
        else:
            result[key] = candidate

    # Names cannot be safely resolved by Excel name alone if repeated across plants.
    for key in ambiguous:
        result.pop(key, None)
    if ambiguous:
        logger.warning('Ambiguous department names across plants: %s', sorted(ambiguous))
    return result, ambiguous


def _row_data(row, dept_info, ambiguous_depts):
    paycode = _string(row.get('Paycode'))
    if not paycode:
        raise ValueError('Paycode is empty')
    name = _string(row.get('EmployeeName'))
    if not name:
        raise ValueError('EmployeeName is empty')
    dept = _department(row.get('Department'))
    if not dept or dept not in APPROVED_DEPARTMENTS:
        raise ValueError(f'Unknown or missing department: {dept!r}')
    if dept in ambiguous_depts:
        raise ValueError(f'Department {dept!r} belongs to multiple plants; cannot assign without Plant column')
    if dept not in dept_info:
        raise ValueError(f'Department {dept!r} not found in dbo.departments; employee skipped')

    data = {}
    for excel_field, model_field in EXCEL_FIELDS.items():
        if model_field not in USER_COLS:
            continue
        value = row.get(excel_field)
        if model_field in ('dob', 'dateOfJoining', 'leavingDate'):
            data[model_field] = _date(value)
        elif model_field in ('sno', 'skillLevel'):
            # DB skillLevel is varchar, even though Excel uses 1/2/3/4.
            data[model_field] = (_string(_integer(value)) if model_field == 'skillLevel' and not _blank(value)
                                 else _integer(value))
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
    address = ' '.join(filter(None, (_string(row.get('Address_1')), _string(row.get('Address_2')))))
    if address:
        if len(address) > 500:
            raise ValueError('Combined address exceeds 500 characters')
        data['address'] = address
    else:
        data['address'] = None

    data['payCode'] = paycode
    data['empName'] = name
    dept_id, plant_id = dept_info[dept]
    data['departmentId'] = dept_id
    data['departmentName'] = dept
    data['plantId'] = plant_id
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
    for field in CLEAR_HIERARCHY_FIELDS:
        if field in USER_COLS:
            data[field] = None
    return data


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
    return query.order_by(User.id).offset(max(skip, 0)).limit(min(max(limit, 1), 1000)).all()


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
        raise HTTPException(400, 'Invalid update: duplicate payCode or hierarchy reference') from e
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
    """Import Excel with validation + batched SQL writes.

    - Existing payCode: update mapped fields, PRESERVE password/role.
    - New payCode: hash DOB (DDMMYYYY), create OPERATOR.
    - Department ID + plant ID come from dbo.departments; hierarchy below dept stays NULL.
    - All successfully validated rows are committed in one transaction.
      If a DB error happens, all writes roll back (no misleading partial success).
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

    # Actual EmployeeMaster.xlsx has 'Shift ' and 'Basic ' column labels.
    df.columns = [str(c).strip() for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise HTTPException(400, 'Duplicate column names after trimming spaces')
    missing = {'Paycode', 'EmployeeName', 'Department'} - set(df.columns)
    if missing:
        raise HTTPException(400, f'Missing Excel columns: {sorted(missing)}')
    required_orm = {'salary', 'hra', 'dob', 'passwordHash', 'departmentId', 'departmentName', 'plantId'}
    missing_orm = required_orm - USER_COLS
    if missing_orm:
        raise HTTPException(500, f'User model missing columns: {sorted(missing_orm)}')

    dept_info, ambiguous_depts = _read_departments(db)
    ignored = [c for c in df.columns if c not in EXCEL_FIELDS and c != 'Address_2']
    errors = []
    skipped = 0
    seen = set()
    rows = []

    for idx, values in enumerate(df.to_dict(orient='records'), start=2):
        if all(_blank(v) for v in values.values()):
            skipped += 1
            continue
        try:
            data = _row_data(values, dept_info, ambiguous_depts)
            pay_code = data['payCode']
            if pay_code in seen:
                raise ValueError(f'Duplicate Paycode in Excel: {pay_code}')
            seen.add(pay_code)
            rows.append((idx, data))
        except (ValueError, TypeError, OverflowError, InvalidOperation) as exc:
            skipped += 1
            errors.append(f'Excel row {idx}: {exc}')

    logger.info('Excel import parsed: %s valid, %s invalid in %.2fs',
                len(rows), skipped, time.perf_counter() - start)
    if not rows:
        return {'totalRows': len(df), 'inserted': 0, 'updated': 0,
                'skipped': skipped, 'errors': errors, 'errorCount': len(errors),
                'ignoredExcelColumns': ignored}

    # Fetch ONLY id/payCode rather than loading every user + all 45 columns.
    # SQL Server limits SQL IN parameters; split lookups into small chunks.
    existing = {}
    codes = [data['payCode'] for _, data in rows]
    try:
        for start_idx in range(0, len(codes), BATCH_SIZE):
            part = codes[start_idx:start_idx+BATCH_SIZE]
            existing.update(db.query(User.payCode, User.id)
                            .filter(User.payCode.in_(part)).all())

        inserts, updates = [], []
        for idx, data in rows:
            code = data['payCode']
            if code in existing:
                # Keep passwords, roles, IDs, createdAt unchanged on Excel update.
                updates.append({'id': existing[code], **data})
            else:
                if data.get('dob') is None:
                    errors.append(f'Excel row {idx}: Date_Of_Birth required for new employee')
                    skipped += 1
                    continue
                inserts.append({**data, 'passwordHash': get_password_hash(_dob_password(data['dob'])),
                                'role': 'OPERATOR', 'active': data.get('active', True)})
            if (len(inserts) + len(updates)) % 100 == 0:
                logger.info('Excel import prepared %s rows in %.2fs',
                            len(inserts) + len(updates), time.perf_counter() - start)

        # SQLAlchemy bulk APIs avoid one ORM flush / SAVEPOINT per employee.
        # BATCH_SIZE also prevents large parameter payloads to MSSQL.
        for offset in range(0, len(updates), BATCH_SIZE):
            db.bulk_update_mappings(User, updates[offset:offset+BATCH_SIZE])
            logger.info('Excel import updated %s/%s', min(offset+BATCH_SIZE, len(updates)), len(updates))
        for offset in range(0, len(inserts), BATCH_SIZE):
            db.bulk_insert_mappings(User, inserts[offset:offset+BATCH_SIZE])
            logger.info('Excel import inserted %s/%s', min(offset+BATCH_SIZE, len(inserts)), len(inserts))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception('Excel import failed; transaction rolled back')
        raise HTTPException(500, 'Excel import failed during database save; changes rolled back. See server log.') from exc
    except Exception:
        db.rollback()
        logger.exception('Excel import unexpectedly failed')
        raise

    elapsed = round(time.perf_counter() - start, 2)
    logger.info('Excel import complete: inserted=%s updated=%s skipped=%s time=%.2fs',
                len(inserts), len(updates), skipped, elapsed)
    return {
        'totalRows': len(df), 'inserted': len(inserts), 'updated': len(updates),
        'skipped': skipped, 'errors': errors, 'errorCount': len(errors),
        'durationSeconds': elapsed,
        'ignoredExcelColumns': ignored,
        'departmentAssignment': 'departmentId and plantId matched from dbo.departments; lower hierarchy NULL',
        'passwordPolicy': 'New users DOB (DDMMYYYY); existing passwords preserved',
        'payMapping': 'Basic to salary, HRA to hra',
    }
