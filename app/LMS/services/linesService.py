from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import HTTPException, status
from app.LMS.models.linesModel import Line
from app.LMS.models.subDepartmentsModel import SubDepartment
from app.LMS.models.departmentsModel import Department
from app.LMS.models.plantsModel import Plant
from app.LMS.models.machineModel import Machine
from app.LMS.schemas.linesSchema import LineCreate, LineUpdate

def getAllLines(
    db: Session,
    plantId: Optional[int] = None,
    departmentId: Optional[int] = None,
    subDepartmentId: Optional[int] = None,
    lineName: Optional[str] = None
) -> List[Line]:
    query = db.query(Line)
    if plantId is not None:
        query = query.filter(Line.plantId == plantId)
    if departmentId is not None:
        query = query.filter(Line.departmentId == departmentId)
    if subDepartmentId is not None:
        query = query.filter(Line.subDepartmentId == subDepartmentId)
    if lineName:
        query = query.filter(Line.lineName.ilike(f"%{lineName}%"))
    return query.all()

def getLineById(db: Session, lineId: int) -> Optional[Line]:
    return db.query(Line).filter(Line.id == lineId).first()

def createLine(db: Session, lineData: LineCreate) -> Line:
    # Validate parent SubDepartment exists
    sub_dept = db.query(SubDepartment).filter(SubDepartment.id == lineData.subDepartmentId).first()
    if not sub_dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SubDepartment with id {lineData.subDepartmentId} does not exist"
        )

    # Validate or auto-infer departmentId
    if lineData.departmentId is not None:
        if lineData.departmentId != sub_dept.departmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SubDepartment {sub_dept.id} belongs to Department {sub_dept.departmentId}, not Department {lineData.departmentId}"
            )
        resolved_dept_id = lineData.departmentId
    else:
        resolved_dept_id = sub_dept.departmentId

    # Validate or auto-infer plantId
    if lineData.plantId is not None:
        if lineData.plantId != sub_dept.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SubDepartment {sub_dept.id} belongs to Plant {sub_dept.plantId}, not Plant {lineData.plantId}"
            )
        resolved_plant_id = lineData.plantId
    else:
        resolved_plant_id = sub_dept.plantId

    newLine = Line(
        plantId=resolved_plant_id,
        departmentId=resolved_dept_id,
        subDepartmentId=lineData.subDepartmentId,
        lineName=lineData.lineName.strip()
    )
    db.add(newLine)
    db.commit()
    db.refresh(newLine)
    return newLine

def updateLine(db: Session, lineId: int, lineData: LineUpdate) -> Optional[Line]:
    line = getLineById(db, lineId)
    if not line:
        return None

    target_subdept_id = lineData.subDepartmentId if lineData.subDepartmentId is not None else line.subDepartmentId
    sub_dept = db.query(SubDepartment).filter(SubDepartment.id == target_subdept_id).first()
    if not sub_dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SubDepartment with id {target_subdept_id} does not exist"
        )

    if lineData.subDepartmentId is not None:
        line.subDepartmentId = lineData.subDepartmentId

    # Update departmentId with validation
    if lineData.departmentId is not None:
        if lineData.departmentId != sub_dept.departmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SubDepartment {sub_dept.id} belongs to Department {sub_dept.departmentId}, not Department {lineData.departmentId}"
            )
        line.departmentId = lineData.departmentId
    elif lineData.subDepartmentId is not None:
        line.departmentId = sub_dept.departmentId

    # Update plantId with validation
    if lineData.plantId is not None:
        if lineData.plantId != sub_dept.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SubDepartment {sub_dept.id} belongs to Plant {sub_dept.plantId}, not Plant {lineData.plantId}"
            )
        line.plantId = lineData.plantId
    elif lineData.subDepartmentId is not None:
        line.plantId = sub_dept.plantId

    if lineData.lineName is not None:
        line.lineName = lineData.lineName.strip()

    db.commit()
    db.refresh(line)
    return line

def deleteLine(db: Session, lineId: int) -> Optional[Line]:
    line = getLineById(db, lineId)
    if not line:
        return None

    # Check for dependent machines
    has_machines = db.query(Machine).filter(Machine.lineId == lineId).first()
    if has_machines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete Line with id {lineId} because it has associated machines."
        )

    db.delete(line)
    db.commit()
    return line
