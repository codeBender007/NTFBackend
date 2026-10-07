from pydantic import BaseModel
from typing import Optional

class MachineCreate(BaseModel):
    departmentId: int
    subDepartmentId: int
    lineId: int
    machineName: str

class MachineUpdate(BaseModel):
    departmentId: Optional[int] = None
    subDepartmentId: Optional[int] = None
    lineId: Optional[int] = None
    machineName: Optional[str] = None

class MachineResponse(BaseModel):
    id: int
    departmentId: int
    subDepartmentId: int
    lineId: int
    machineName: str

    class Config:
        from_attributes = True