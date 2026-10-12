from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import HTTPException, status
from app.LMS.models.subDepartmentsModel import SubDepartment
from app.LMS.models.departmentsModel import Department
from app.LMS.models.plantsModel import Plant
from app.LMS.models.linesModel import Line
from app.LMS.schemas.subDepartmentsSchema import SubDepartmentCreate, SubDepartmentUpdate

def getAllSubDepartments(
    db: Session,
    plantId: Optional[int] = None,
    departmentId: Optional[int] = None,
    subDepartmentName: Optional[str] = None
) -> List[SubDepartment]:
    query = db.query(SubDepartment)
    if plantId is not None:
        query = query.filter(SubDepartment.plantId == plantId)
    if departmentId is not None:
        query = query.filter(SubDepartment.departmentId == departmentId)
    if subDepartmentName:
        query = query.filter(SubDepartment.subDepartmentName.ilike(f"%{subDepartmentName}%"))
    return query.all()

def getSubDepartmentById(db: Session, subDepartmentId: int) -> Optional[SubDepartment]:
    return db.query(SubDepartment).filter(SubDepartment.id == subDepartmentId).first()

def createSubDepartment(db: Session, subDepartmentData: SubDepartmentCreate) -> SubDepartment:
    # Validate parent Department exists
    dept = db.query(Department).filter(Department.id == subDepartmentData.departmentId).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {subDepartmentData.departmentId} does not exist"
        )

    # Validate hierarchy for plantId
    if subDepartmentData.plantId is not None:
        plant = db.query(Plant).filter(Plant.id == subDepartmentData.plantId).first()
        if not plant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plant with id {subDepartmentData.plantId} does not exist"
            )
        if dept.plantId != subDepartmentData.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with id {dept.id} belongs to Plant {dept.plantId}, not Plant {subDepartmentData.plantId}"
            )
        resolved_plant_id = subDepartmentData.plantId
    else:
        resolved_plant_id = dept.plantId

    newSubDepartment = SubDepartment(
        plantId=resolved_plant_id,
        departmentId=subDepartmentData.departmentId,
        subDepartmentName=subDepartmentData.subDepartmentName.strip()
    )
    db.add(newSubDepartment)
    db.commit()
    db.refresh(newSubDepartment)
    return newSubDepartment

def updateSubDepartment(db: Session, subDepartmentId: int, subDepartmentData: SubDepartmentUpdate) -> Optional[SubDepartment]:
    subDepartment = getSubDepartmentById(db, subDepartmentId)
    if not subDepartment:
        return None

    # Handle departmentId update
    target_dept_id = subDepartmentData.departmentId if subDepartmentData.departmentId is not None else subDepartment.departmentId
    dept = db.query(Department).filter(Department.id == target_dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {target_dept_id} does not exist"
        )

    if subDepartmentData.departmentId is not None:
        subDepartment.departmentId = subDepartmentData.departmentId

    # Handle plantId update
    if subDepartmentData.plantId is not None:
        plant = db.query(Plant).filter(Plant.id == subDepartmentData.plantId).first()
        if not plant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plant with id {subDepartmentData.plantId} does not exist"
            )
        if dept.plantId != subDepartmentData.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with id {dept.id} belongs to Plant {dept.plantId}, not Plant {subDepartmentData.plantId}"
            )
        subDepartment.plantId = subDepartmentData.plantId
    elif subDepartmentData.departmentId is not None:
        # If department was changed without specifying plant, align plant with new department
        subDepartment.plantId = dept.plantId

    if subDepartmentData.subDepartmentName is not None:
        subDepartment.subDepartmentName = subDepartmentData.subDepartmentName.strip()

    db.commit()
    db.refresh(subDepartment)
    return subDepartment

def deleteSubDepartment(db: Session, subDepartmentId: int) -> Optional[SubDepartment]:
    subDepartment = getSubDepartmentById(db, subDepartmentId)
    if not subDepartment:
        return None

    # Check for dependent lines
    has_lines = db.query(Line).filter(Line.subDepartmentId == subDepartmentId).first()
    if has_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete SubDepartment with id {subDepartmentId} because it has associated lines."
        )

    db.delete(subDepartment)
    db.commit()
    return subDepartment
