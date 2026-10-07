from sqlalchemy.orm import Session
from app.models.subDepartmentsModel import SubDepartment
from app.schemas.subDepartmentsSchema import SubDepartmentCreate, SubDepartmentUpdate

def getAllSubDepartments(db: Session, departmentId: int = None):
    query = db.query(SubDepartment)
    if departmentId:
        query = query.filter(SubDepartment.departmentId == departmentId)
    return query.all()

def getSubDepartmentById(db: Session, subDepartmentId: int):
    return db.query(SubDepartment).filter(SubDepartment.id == subDepartmentId).first()

def createSubDepartment(db: Session, subDepartmentData: SubDepartmentCreate):
    newSubDepartment = SubDepartment(
        departmentId=subDepartmentData.departmentId,
        subDepartmentName=subDepartmentData.subDepartmentName
    )
    db.add(newSubDepartment)
    db.commit()
    db.refresh(newSubDepartment)
    return newSubDepartment

def updateSubDepartment(db: Session, subDepartmentId: int, subDepartmentData: SubDepartmentUpdate):
    subDepartment = getSubDepartmentById(db, subDepartmentId)
    if not subDepartment:
        return None
    if subDepartmentData.departmentId is not None:
        subDepartment.departmentId = subDepartmentData.departmentId
    if subDepartmentData.subDepartmentName is not None:
        subDepartment.subDepartmentName = subDepartmentData.subDepartmentName
    db.commit()
    db.refresh(subDepartment)
    return subDepartment

def deleteSubDepartment(db: Session, subDepartmentId: int):
    subDepartment = getSubDepartmentById(db, subDepartmentId)
    if not subDepartment:
        return None
    db.delete(subDepartment)
    db.commit()
    return subDepartment