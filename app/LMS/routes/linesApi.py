from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.LMS.schemas.linesSchema import LineCreate, LineUpdate, LineResponse
from app.LMS.schemas.machineSchema import MachineResponse
from app.LMS.services import linesService, machineService

router = APIRouter(prefix="/lines", tags=["Lines"])

@router.get("/", response_model=List[LineResponse])
def getLines(
    plantId: Optional[int] = Query(None, description="Filter lines by plant ID"),
    departmentId: Optional[int] = Query(None, description="Filter lines by department ID"),
    subDepartmentId: Optional[int] = Query(None, description="Filter lines by sub-department ID"),
    lineName: Optional[str] = Query(None, description="Filter lines by line name"),
    db: Session = Depends(get_db)
):
    return linesService.getAllLines(
        db,
        plantId=plantId,
        departmentId=departmentId,
        subDepartmentId=subDepartmentId,
        lineName=lineName
    )

@router.get("/{lineId}", response_model=LineResponse)
def getLine(lineId: int, db: Session = Depends(get_db)):
    line = linesService.getLineById(db, lineId)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line not found")
    return line

@router.post("/", response_model=LineResponse, status_code=status.HTTP_201_CREATED)
def createLine(lineData: LineCreate, db: Session = Depends(get_db)):
    return linesService.createLine(db, lineData)

@router.put("/{lineId}", response_model=LineResponse)
def updateLine(lineId: int, lineData: LineUpdate, db: Session = Depends(get_db)):
    line = linesService.updateLine(db, lineId, lineData)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line not found")
    return line

@router.delete("/{lineId}", status_code=status.HTTP_200_OK)
def deleteLine(lineId: int, db: Session = Depends(get_db)):
    line = linesService.deleteLine(db, lineId)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line not found")
    return {"message": "Line deleted successfully"}

# Cascading lookup: Get all machines for a given line
@router.get("/{lineId}/machines", response_model=List[MachineResponse])
def getMachinesByLine(lineId: int, db: Session = Depends(get_db)):
    line = linesService.getLineById(db, lineId)
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line not found")
    return machineService.getAllMachines(db, lineId=lineId)
