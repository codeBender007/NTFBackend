from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Data create karte waqt (Request Body)
class LineCreate(BaseModel):
    plantId: Optional[int] = Field(None, gt=0, description="Parent plant ID (optional; auto-inferred from hierarchy if omitted)")
    departmentId: Optional[int] = Field(None, gt=0, description="Parent department ID (optional; auto-inferred from subDepartment if omitted)")
    subDepartmentId: int = Field(..., gt=0, description="Parent subDepartment ID")
    lineName: str = Field(..., min_length=1, max_length=150, description="Line name")

# Data update karte waqt
class LineUpdate(BaseModel):
    plantId: Optional[int] = Field(None, gt=0, description="Updated plant ID")
    departmentId: Optional[int] = Field(None, gt=0, description="Updated department ID")
    subDepartmentId: Optional[int] = Field(None, gt=0, description="Updated subDepartment ID")
    lineName: Optional[str] = Field(None, min_length=1, max_length=150, description="Updated line name")

# API se response bhejte waqt
class LineResponse(BaseModel):
    id: int
    plantId: int
    departmentId: int
    subDepartmentId: int
    lineName: str

    model_config = ConfigDict(from_attributes=True)