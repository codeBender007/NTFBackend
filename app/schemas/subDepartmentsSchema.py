from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Data create karte waqt (Request Body)
class SubDepartmentCreate(BaseModel):
    plantId: Optional[int] = Field(None, gt=0, description="Parent plant ID (optional; auto-inferred from department if omitted)")
    departmentId: int = Field(..., gt=0, description="Parent department ID")
    subDepartmentName: str = Field(..., min_length=1, max_length=150, description="SubDepartment name")

# Data update karte waqt
class SubDepartmentUpdate(BaseModel):
    plantId: Optional[int] = Field(None, gt=0, description="Updated plant ID")
    departmentId: Optional[int] = Field(None, gt=0, description="Updated department ID")
    subDepartmentName: Optional[str] = Field(None, min_length=1, max_length=150, description="Updated subDepartment name")

# API se response bhejte waqt
class SubDepartmentResponse(BaseModel):
    id: int
    plantId: int
    departmentId: int
    subDepartmentName: str

    model_config = ConfigDict(from_attributes=True)