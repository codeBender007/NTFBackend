from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Data create karte waqt (Request Body)
class DepartmentCreate(BaseModel):
    plantId: int = Field(..., gt=0, description="Parent plant ID")
    departmentName: str = Field(..., min_length=1, max_length=150, description="Department name")

# Data update karte waqt
class DepartmentUpdate(BaseModel):
    plantId: Optional[int] = Field(None, gt=0, description="Updated parent plant ID")
    departmentName: Optional[str] = Field(None, min_length=1, max_length=150, description="Updated department name")

# API se response bhejte waqt
class DepartmentResponse(BaseModel):
    id: int
    plantId: int
    departmentName: str

    model_config = ConfigDict(from_attributes=True)
