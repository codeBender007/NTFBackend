from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Data create karte waqt (Request Body)
class MachineCreate(BaseModel):
    plantId: Optional[int] = Field(None, gt=0, description="Parent plant ID (optional; auto-inferred from hierarchy if omitted)")
    departmentId: Optional[int] = Field(None, gt=0, description="Parent department ID (optional; auto-inferred from hierarchy if omitted)")
    subDepartmentId: Optional[int] = Field(None, gt=0, description="Parent subDepartment ID (optional; auto-inferred from line if omitted)")
    lineId: int = Field(..., gt=0, description="Parent line ID")
    machineName: str = Field(..., min_length=1, max_length=150, description="Machine name")

# Data update karte waqt
class MachineUpdate(BaseModel):
    plantId: Optional[int] = Field(None, gt=0, description="Updated plant ID")
    departmentId: Optional[int] = Field(None, gt=0, description="Updated department ID")
    subDepartmentId: Optional[int] = Field(None, gt=0, description="Updated subDepartment ID")
    lineId: Optional[int] = Field(None, gt=0, description="Updated line ID")
    machineName: Optional[str] = Field(None, min_length=1, max_length=150, description="Updated machine name")

# API se response bhejte waqt
class MachineResponse(BaseModel):
    id: int
    plantId: int
    departmentId: int
    subDepartmentId: int
    lineId: int
    machineName: str

    model_config = ConfigDict(from_attributes=True)
