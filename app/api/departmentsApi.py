from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.schemas.departmentsSchema import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.schemas.subDepartmentsSchema import SubDepartmentResponse
from app.services import departmentsService, subDepartmentsService

router = APIRouter(prefix="/departments", tags=["Departments"])

@router.get("/", response_model=List[DepartmentResponse])
def getDepartments(
    plantId: Optional[int] = Query(None, description="Filter departments by plant ID"),
    departmentName: Optional[str] = Query(None, description="Filter departments by name"),
    db: Session = Depends(get_db)
):
    return departmentsService.getAllDepartments(db, plantId=plantId, departmentName=departmentName)

@router.get("/{departmentId}", response_model=DepartmentResponse)
def getDepartment(departmentId: int, db: Session = Depends(get_db)):
    dept = departmentsService.getDepartmentById(db, departmentId)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept

@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def createDepartment(deptData: DepartmentCreate, db: Session = Depends(get_db)):
    return departmentsService.createDepartment(db, deptData)

@router.put("/{departmentId}", response_model=DepartmentResponse)
def updateDepartment(departmentId: int, deptData: DepartmentUpdate, db: Session = Depends(get_db)):
    dept = departmentsService.updateDepartment(db, departmentId, deptData)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept

@router.delete("/{departmentId}", status_code=status.HTTP_200_OK)
def deleteDepartment(departmentId: int, db: Session = Depends(get_db)):
    dept = departmentsService.deleteDepartment(db, departmentId)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return {"message": "Department deleted successfully"}

# Cascading lookup: Get all sub-departments for a given department
@router.get("/{departmentId}/sub-departments", response_model=List[SubDepartmentResponse], tags=["Departments", "Sub Departments"])
def getSubDepartmentsByDepartment(departmentId: int, db: Session = Depends(get_db)):
    dept = departmentsService.getDepartmentById(db, departmentId)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return subDepartmentsService.getAllSubDepartments(db, departmentId=departmentId)