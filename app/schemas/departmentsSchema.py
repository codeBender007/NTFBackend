from pydantic import BaseModel
from typing import Optional

# Data create karte waqt (Request Body)
class DepartmentCreate(BaseModel):
    departmentName: str

# Data update karte waqt
class DepartmentUpdate(BaseModel):
    departmentName: Optional[str] = None

# API se response bhejte waqt
class DepartmentResponse(BaseModel):
    id: int
    departmentName: str

    class Config:
        from_attributes = True