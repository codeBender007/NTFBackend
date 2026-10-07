from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.schemas.machineSchema import MachineCreate, MachineUpdate, MachineResponse
from app.services import machineService

# Ye variable name 'router' hona zaroori hai:
router = APIRouter(prefix="/machines", tags=["Machines"])

@router.get("/", response_model=List[MachineResponse])
def getMachines(
    departmentId: Optional[int] = Query(None),
    subDepartmentId: Optional[int] = Query(None),
    lineId: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    return machineService.getAllMachines(
        db, departmentId=departmentId, subDepartmentId=subDepartmentId, lineId=lineId
    )

@router.get("/{machineId}", response_model=MachineResponse)
def getMachine(machineId: int, db: Session = Depends(get_db)):
    machine = machineService.getMachineById(db, machineId)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
    return machine

@router.post("/", response_model=MachineResponse, status_code=status.HTTP_201_CREATED)
def createMachine(machineData: MachineCreate, db: Session = Depends(get_db)):
    return machineService.createMachine(db, machineData)

@router.put("/{machineId}", response_model=MachineResponse)
def updateMachine(machineId: int, machineData: MachineUpdate, db: Session = Depends(get_db)):
    machine = machineService.updateMachine(db, machineId, machineData)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
    return machine

@router.delete("/{machineId}", status_code=status.HTTP_200_OK)
def deleteMachine(machineId: int, db: Session = Depends(get_db)):
    machine = machineService.deleteMachine(db, machineId)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
    return {"message": "Machine deleted successfully"}