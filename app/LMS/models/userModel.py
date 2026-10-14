from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import synonym
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    payCode = Column(String(50), unique=True, index=True, nullable=False)
    cardNo = Column(String(50))
    empName = Column(String(150), nullable=False)
    dob = Column(Date)
    dateOfJoining = Column(Date)
    leavingDate = Column(Date)

    plantId = Column(Integer, ForeignKey("plants.id"))
    plantLocation = Column(String(150))
    departmentId = Column(Integer, ForeignKey("departments.id"))
    departmentName = Column(String(150))
    subDepartmentId = Column(Integer, ForeignKey("subDepartments.id"))
    subDepartmentName = Column(String(150))
    lineId = Column(Integer, ForeignKey("lines.id"))
    lineName = Column(String(150))
    machineId = Column(Integer, ForeignKey("machines.id"))
    machineName = Column(String(150))

    shift = Column(String(20))
    companyName = Column(String(150))
    category = Column(String(50))
    grade = Column(String(50))
    designation = Column(String(100))
    skillLevel = Column(String(50))
    isDojo = Column(Boolean, default=False)
    firstOfDay = Column(String(50))

    gender = Column(String(20))
    bloodGroup = Column(String(10))
    fatherName = Column(String(150))
    maritalStatus = Column(String(30))
    email = Column(String(150))
    mobileNo = Column(String(20))
    address = Column(String(500))
    states = Column(String(100))
    pinCode = Column(String(20))
    bankAccount = Column(String(50))
    salary = Column(Numeric(18, 2))
    hra = Column(Numeric(18, 2))
    pfNo = Column(String(50))
    panNo = Column(String(30))
    esiNo = Column(String(50))
    aadharNo = Column(String(30))

    passwordHash = Column(String(255))
    role = Column(String(50), default="OPERATOR")
    active = Column(Boolean, default=True)
    createdAt = Column(DateTime, server_default=func.getdate())
    updatedAt = Column(DateTime, server_default=func.getdate(), onupdate=func.getdate())

    # Compatibility synonyms for query and attribute access
    is_active = synonym("active")
    password_hash = synonym("passwordHash")
