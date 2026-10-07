from pydantic import BaseModel
from typing import Optional

class SubDepartmentCreate(BaseModel):
    departmentId: int
    subDepartmentName: str

class SubDepartmentUpdate(BaseModel):
    departmentId: Optional[int] = None
    subDepartmentName: Optional[str] = None

class SubDepartmentResponse(BaseModel):
    id: int
    departmentId: int
    subDepartmentName: str

    class Config:
        from_attributes = True