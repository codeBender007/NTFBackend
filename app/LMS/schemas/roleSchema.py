from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.LMS.schemas.rolePermissionSchema import RolePermissionPageResponse


class RoleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Unique role name")
    isActive: Optional[bool] = Field(default=True, description="Role active status")


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    isActive: Optional[bool] = True


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    isActive: Optional[bool] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    isActive: bool = True

    model_config = ConfigDict(from_attributes=True)


class RoleDetailResponse(RoleResponse):
    permissions: List[RolePermissionPageResponse] = []

    model_config = ConfigDict(from_attributes=True)
