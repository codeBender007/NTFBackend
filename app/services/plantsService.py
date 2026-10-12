from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi import HTTPException, status
from app.models.plantsModel import Plant
from app.models.departmentsModel import Department
from app.schemas.plantsSchema import PlantCreate, PlantUpdate

def getAllPlants(db: Session, plantName: Optional[str] = None) -> List[Plant]:
    query = db.query(Plant)
    if plantName:
        query = query.filter(Plant.plantName.ilike(f"%{plantName}%"))
    return query.all()

def getPlantById(db: Session, plantId: int) -> Optional[Plant]:
    return db.query(Plant).filter(Plant.id == plantId).first()

def createPlant(db: Session, plantData: PlantCreate) -> Plant:
    newPlant = Plant(plantName=plantData.plantName.strip())
    db.add(newPlant)
    db.commit()
    db.refresh(newPlant)
    return newPlant

def updatePlant(db: Session, plantId: int, plantData: PlantUpdate) -> Optional[Plant]:
    plant = getPlantById(db, plantId)
    if not plant:
        return None
    if plantData.plantName is not None:
        plant.plantName = plantData.plantName.strip()
    db.commit()
    db.refresh(plant)
    return plant

def deletePlant(db: Session, plantId: int) -> Optional[Plant]:
    plant = getPlantById(db, plantId)
    if not plant:
        return None

    # Check for dependent departments to avoid foreign key integrity errors
    has_departments = db.query(Department).filter(Department.plantId == plantId).first()
    if has_departments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete Plant with id {plantId} because it has associated departments."
        )

    db.delete(plant)
    db.commit()
    return plant
