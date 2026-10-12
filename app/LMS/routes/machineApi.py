from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.LMS.schemas.machineSchema import MachineCreate, MachineUpdate, MachineResponse
from app.LMS.services import machineService

router = APIRouter(prefix="/machines", tags=["Machines"])

@router.get("/", response_model=List[MachineResponse])
def getMachines(
    plantId: Optional[int] = Query(None, description="Filter machines by plant ID"),
    departmentId: Optional[int] = Query(None, description="Filter machines by department ID"),
    subDepartmentId: Optional[int] = Query(None, description="Filter machines by sub-department ID"),
    lineId: Optional[int] = Query(None, description="Filter machines by line ID"),
    machineName: Optional[str] = Query(None, description="Filter machines by machine name"),
    db: Session = Depends(get_db)
):
    return machineService.getAllMachines(
        db,
        plantId=plantId,
        departmentId=departmentId,
        subDepartmentId=subDepartmentId,
        lineId=lineId,
        machineName=machineName
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
