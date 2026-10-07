from pydantic import BaseModel
from typing import Optional

class LineCreate(BaseModel):
    departmentId: int
    subDepartmentId: int
    lineName: str

class LineUpdate(BaseModel):
    departmentId: Optional[int] = None
    subDepartmentId: Optional[int] = None
    lineName: Optional[str] = None

class LineResponse(BaseModel):
    id: int
    departmentId: int
    subDepartmentId: int
    lineName: str

    class Config:
        from_attributes = True