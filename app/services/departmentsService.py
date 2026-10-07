from sqlalchemy.orm import Session
from app.models.departmentsModel import Department
from app.schemas.departmentsSchema import DepartmentCreate, DepartmentUpdate

def getAllDepartments(db: Session):
    return db.query(Department).all()

def getDepartmentById(db: Session, departmentId: int):
    return db.query(Department).filter(Department.id == departmentId).first()

def createDepartment(db: Session, departmentData: DepartmentCreate):
    newDepartment = Department(departmentName=departmentData.departmentName)
    db.add(newDepartment)
    db.commit()
    db.refresh(newDepartment)
    return newDepartment

def updateDepartment(db: Session, departmentId: int, departmentData: DepartmentUpdate):
    department = getDepartmentById(db, departmentId)
    if not department:
        return None
    if departmentData.departmentName is not None:
        department.departmentName = departmentData.departmentName
    db.commit()
    db.refresh(department)
    return department

def deleteDepartment(db: Session, departmentId: int):
    department = getDepartmentById(db, departmentId)
    if not department:
        return None
    db.delete(department)
    db.commit()
    return department