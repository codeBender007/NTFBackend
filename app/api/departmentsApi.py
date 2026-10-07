from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.departmentsSchema import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.services import departmentsService

router = APIRouter(prefix="/departments", tags=["Departments"])

@router.get("/", response_model=List[DepartmentResponse])
def getDepartments(db: Session = Depends(get_db)):
    return departmentsService.getAllDepartments(db)

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