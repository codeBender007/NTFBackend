from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.schemas.subDepartmentsSchema import SubDepartmentCreate, SubDepartmentUpdate, SubDepartmentResponse
from app.services import subDepartmentsService

router = APIRouter(prefix="/sub-departments", tags=["Sub Departments"])

@router.get("/", response_model=List[SubDepartmentResponse])
def getSubDepartments(departmentId: Optional[int] = Query(None), db: Session = Depends(get_db)):
    return subDepartmentsService.getAllSubDepartments(db, departmentId=departmentId)

@router.get("/{subDepartmentId}", response_model=SubDepartmentResponse)
def getSubDepartment(subDepartmentId: int, db: Session = Depends(get_db)):
    subDept = subDepartmentsService.getSubDepartmentById(db, subDepartmentId)
    if not subDept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SubDepartment not found")
    return subDept

@router.post("/", response_model=SubDepartmentResponse, status_code=status.HTTP_201_CREATED)
def createSubDepartment(subDeptData: SubDepartmentCreate, db: Session = Depends(get_db)):
    return subDepartmentsService.createSubDepartment(db, subDeptData)

@router.put("/{subDepartmentId}", response_model=SubDepartmentResponse)
def updateSubDepartment(subDepartmentId: int, subDeptData: SubDepartmentUpdate, db: Session = Depends(get_db)):
    subDept = subDepartmentsService.updateSubDepartment(db, subDepartmentId, subDeptData)
    if not subDept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SubDepartment not found")
    return subDept

@router.delete("/{subDepartmentId}", status_code=status.HTTP_200_OK)
def deleteSubDepartment(subDepartmentId: int, db: Session = Depends(get_db)):
    subDept = subDepartmentsService.deleteSubDepartment(db, subDepartmentId)
    if not subDept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SubDepartment not found")
    return {"message": "SubDepartment deleted successfully"}