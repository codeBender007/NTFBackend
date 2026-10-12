from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import HTTPException, status
from app.models.machineModel import Machine
from app.models.linesModel import Line
from app.schemas.machineSchema import MachineCreate, MachineUpdate

def getAllMachines(
    db: Session,
    plantId: Optional[int] = None,
    departmentId: Optional[int] = None,
    subDepartmentId: Optional[int] = None,
    lineId: Optional[int] = None,
    machineName: Optional[str] = None
) -> List[Machine]:
    query = db.query(Machine)
    if plantId is not None:
        query = query.filter(Machine.plantId == plantId)
    if departmentId is not None:
        query = query.filter(Machine.departmentId == departmentId)
    if subDepartmentId is not None:
        query = query.filter(Machine.subDepartmentId == subDepartmentId)
    if lineId is not None:
        query = query.filter(Machine.lineId == lineId)
    if machineName:
        query = query.filter(Machine.machineName.ilike(f"%{machineName}%"))
    return query.all()

def getMachineById(db: Session, machineId: int) -> Optional[Machine]:
    return db.query(Machine).filter(Machine.id == machineId).first()

def createMachine(db: Session, machineData: MachineCreate) -> Machine:
    # Validate parent Line exists
    line = db.query(Line).filter(Line.id == machineData.lineId).first()
    if not line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line with id {machineData.lineId} does not exist"
        )

    # Validate or auto-infer subDepartmentId
    if machineData.subDepartmentId is not None:
        if machineData.subDepartmentId != line.subDepartmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.id} belongs to SubDepartment {line.subDepartmentId}, not SubDepartment {machineData.subDepartmentId}"
            )
        resolved_subdept_id = machineData.subDepartmentId
    else:
        resolved_subdept_id = line.subDepartmentId

    # Validate or auto-infer departmentId
    if machineData.departmentId is not None:
        if machineData.departmentId != line.departmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.id} belongs to Department {line.departmentId}, not Department {machineData.departmentId}"
            )
        resolved_dept_id = machineData.departmentId
    else:
        resolved_dept_id = line.departmentId

    # Validate or auto-infer plantId
    if machineData.plantId is not None:
        if machineData.plantId != line.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.id} belongs to Plant {line.plantId}, not Plant {machineData.plantId}"
            )
        resolved_plant_id = machineData.plantId
    else:
        resolved_plant_id = line.plantId

    newMachine = Machine(
        plantId=resolved_plant_id,
        departmentId=resolved_dept_id,
        subDepartmentId=resolved_subdept_id,
        lineId=machineData.lineId,
        machineName=machineData.machineName.strip()
    )
    db.add(newMachine)
    db.commit()
    db.refresh(newMachine)
    return newMachine

def updateMachine(db: Session, machineId: int, machineData: MachineUpdate) -> Optional[Machine]:
    machine = getMachineById(db, machineId)
    if not machine:
        return None

    target_line_id = machineData.lineId if machineData.lineId is not None else machine.lineId
    line = db.query(Line).filter(Line.id == target_line_id).first()
    if not line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line with id {target_line_id} does not exist"
        )

    if machineData.lineId is not None:
        machine.lineId = machineData.lineId

    # Validate or update subDepartmentId
    if machineData.subDepartmentId is not None:
        if machineData.subDepartmentId != line.subDepartmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.id} belongs to SubDepartment {line.subDepartmentId}, not SubDepartment {machineData.subDepartmentId}"
            )
        machine.subDepartmentId = machineData.subDepartmentId
    elif machineData.lineId is not None:
        machine.subDepartmentId = line.subDepartmentId

    # Validate or update departmentId
    if machineData.departmentId is not None:
        if machineData.departmentId != line.departmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.id} belongs to Department {line.departmentId}, not Department {machineData.departmentId}"
            )
        machine.departmentId = machineData.departmentId
    elif machineData.lineId is not None:
        machine.departmentId = line.departmentId

    # Validate or update plantId
    if machineData.plantId is not None:
        if machineData.plantId != line.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.id} belongs to Plant {line.plantId}, not Plant {machineData.plantId}"
            )
        machine.plantId = machineData.plantId
    elif machineData.lineId is not None:
        machine.plantId = line.plantId

    if machineData.machineName is not None:
        machine.machineName = machineData.machineName.strip()

    db.commit()
    db.refresh(machine)
    return machine

def deleteMachine(db: Session, machineId: int) -> Optional[Machine]:
    machine = getMachineById(db, machineId)
    if not machine:
        return None
    db.delete(machine)
    db.commit()
    return machine