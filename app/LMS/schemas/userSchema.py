
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class UserBase(BaseModel):
    sno: Optional[int] = None
    payCode: str
    cardNo: Optional[str] = None
    empName: str
    dob: Optional[date] = None
    dateOfJoining: Optional[date] = None
    leavingDate: Optional[date] = None

    plantId: Optional[int] = None
    plantLocation: Optional[str] = None
    departmentId: Optional[int] = None
    departmentName: Optional[str] = None
    subDepartmentId: Optional[int] = None
    subDepartmentName: Optional[str] = None
    lineId: Optional[int] = None
    lineName: Optional[str] = None
    machineId: Optional[int] = None
    machineName: Optional[str] = None

    shift: Optional[str] = None
    companyName: Optional[str] = None
    category: Optional[str] = None
    grade: Optional[str] = None
    designation: Optional[str] = None
    skillLevel: Optional[str] = None
    isDojo: Optional[bool] = False
    firstOfDay: Optional[str] = None

    gender: Optional[str] = None
    bloodGroup: Optional[str] = None
    fatherName: Optional[str] = None
    maritalStatus: Optional[str] = None

    email: Optional[EmailStr] = None
    mobileNo: Optional[str] = None
    address: Optional[str] = None
    states: Optional[str] = None
    pinCode: Optional[str] = None

    bankAccount: Optional[str] = None
    salary: Optional[Decimal] = None
    hra: Optional[Decimal] = None
    pfNo: Optional[str] = None
    panNo: Optional[str] = None
    esiNo: Optional[str] = None
    aadharNo: Optional[str] = None

    role: Optional[str] = "OPERATOR"
    active: Optional[bool] = True


class UserCreate(UserBase):
    password: Optional[str] = "Welcome@123"


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sno: Optional[int] = None
    payCode: Optional[str] = None
    cardNo: Optional[str] = None
    empName: Optional[str] = None
    dob: Optional[date] = None
    dateOfJoining: Optional[date] = None
    leavingDate: Optional[date] = None

    plantId: Optional[int] = None
    plantLocation: Optional[str] = None
    departmentId: Optional[int] = None
    departmentName: Optional[str] = None
    subDepartmentId: Optional[int] = None
    subDepartmentName: Optional[str] = None
    lineId: Optional[int] = None
    lineName: Optional[str] = None
    machineId: Optional[int] = None
    machineName: Optional[str] = None

    shift: Optional[str] = None
    companyName: Optional[str] = None
    category: Optional[str] = None
    grade: Optional[str] = None
    designation: Optional[str] = None
    skillLevel: Optional[str] = None
    isDojo: Optional[bool] = None
    firstOfDay: Optional[str] = None

    gender: Optional[str] = None
    bloodGroup: Optional[str] = None
    fatherName: Optional[str] = None
    maritalStatus: Optional[str] = None

    email: Optional[EmailStr] = None
    mobileNo: Optional[str] = None
    address: Optional[str] = None
    states: Optional[str] = None
    pinCode: Optional[str] = None

    bankAccount: Optional[str] = None
    salary: Optional[Decimal] = None
    hra: Optional[Decimal] = None
    pfNo: Optional[str] = None
    panNo: Optional[str] = None
    esiNo: Optional[str] = None
    aadharNo: Optional[str] = None

    role: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    id: int
    createdAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ExcelUploadResponse(BaseModel):
    totalRows: int
    inserted: int
    updated: int
    skipped: Optional[int] = 0
    errorCount: Optional[int] = 0
    errors: list[str] = []
    ignoredExcelColumns: Optional[list[str]] = []
    departmentAssignment: Optional[str] = None
