from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.schemas.plantsSchema import PlantCreate, PlantUpdate, PlantResponse
from app.schemas.departmentsSchema import DepartmentResponse
from app.services import plantsService, departmentsService

router = APIRouter(prefix="/plants", tags=["Plants"])

@router.get("/", response_model=List[PlantResponse])
def getPlants(
    plantName: Optional[str] = Query(None, description="Filter by plant name"),
    db: Session = Depends(get_db)
):
    return plantsService.getAllPlants(db, plantName=plantName)

@router.get("/{plantId}", response_model=PlantResponse)
def getPlant(plantId: int, db: Session = Depends(get_db)):
    plant = plantsService.getPlantById(db, plantId)
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")
    return plant

@router.post("/", response_model=PlantResponse, status_code=status.HTTP_201_CREATED)
def createPlant(plantData: PlantCreate, db: Session = Depends(get_db)):
    return plantsService.createPlant(db, plantData)

@router.put("/{plantId}", response_model=PlantResponse)
def updatePlant(plantId: int, plantData: PlantUpdate, db: Session = Depends(get_db)):
    plant = plantsService.updatePlant(db, plantId, plantData)
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")
    return plant

@router.delete("/{plantId}", status_code=status.HTTP_200_OK)
def deletePlant(plantId: int, db: Session = Depends(get_db)):
    plant = plantsService.deletePlant(db, plantId)
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")
    return {"message": "Plant deleted successfully"}

# Cascading lookup: Get all departments for a given plant
@router.get("/{plantId}/departments", response_model=List[DepartmentResponse], tags=["Plants", "Departments"])
def getDepartmentsByPlant(plantId: int, db: Session = Depends(get_db)):
    plant = plantsService.getPlantById(db, plantId)
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")
    return departmentsService.getAllDepartments(db, plantId=plantId)
