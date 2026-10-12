from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import HTTPException, status
from app.models.departmentsModel import Department
from app.models.plantsModel import Plant
from app.models.subDepartmentsModel import SubDepartment
from app.schemas.departmentsSchema import DepartmentCreate, DepartmentUpdate

def getAllDepartments(
    db: Session,
    plantId: Optional[int] = None,
    departmentName: Optional[str] = None
) -> List[Department]:
    query = db.query(Department)
    if plantId is not None:
        query = query.filter(Department.plantId == plantId)
    if departmentName:
        query = query.filter(Department.departmentName.ilike(f"%{departmentName}%"))
    return query.all()

def getDepartmentById(db: Session, departmentId: int) -> Optional[Department]:
    return db.query(Department).filter(Department.id == departmentId).first()

def createDepartment(db: Session, departmentData: DepartmentCreate) -> Department:
    # Parent Plant existence validation
    plant = db.query(Plant).filter(Plant.id == departmentData.plantId).first()
    if not plant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plant with id {departmentData.plantId} does not exist"
        )

    newDepartment = Department(
        plantId=departmentData.plantId,
        departmentName=departmentData.departmentName.strip()
    )
    db.add(newDepartment)
    db.commit()
    db.refresh(newDepartment)
    return newDepartment

def updateDepartment(db: Session, departmentId: int, departmentData: DepartmentUpdate) -> Optional[Department]:
    department = getDepartmentById(db, departmentId)
    if not department:
        return None

    if departmentData.plantId is not None:
        plant = db.query(Plant).filter(Plant.id == departmentData.plantId).first()
        if not plant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plant with id {departmentData.plantId} does not exist"
            )
        department.plantId = departmentData.plantId

    if departmentData.departmentName is not None:
        department.departmentName = departmentData.departmentName.strip()

    db.commit()
    db.refresh(department)
    return department

def deleteDepartment(db: Session, departmentId: int) -> Optional[Department]:
    department = getDepartmentById(db, departmentId)
    if not department:
        return None

    # Check for dependent sub-departments
    has_subdepts = db.query(SubDepartment).filter(SubDepartment.departmentId == departmentId).first()
    if has_subdepts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete Department with id {departmentId} because it has associated sub-departments."
        )

    db.delete(department)
    db.commit()
    return department