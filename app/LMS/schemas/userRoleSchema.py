from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class AssignUserRoleRequest(BaseModel):
    roleId: int = Field(..., description="Target role ID to assign to the user")


class UserRoleSummary(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class AssignUserRoleResponse(BaseModel):
    userId: int
    empName: str
    email: Optional[str] = None
    roleId: Optional[int] = None
    roleName: Optional[str] = None
    message: str


class EffectivePermissionItem(BaseModel):
    module: str
    page: str
    pageKey: str
    canView: bool = False
    canCreate: bool = False
    canEdit: bool = False
    canDelete: bool = False
    canUploadExcel: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserEffectivePermissionsResponse(BaseModel):
    userId: int
    role: Optional[UserRoleSummary] = None
    permissions: List[EffectivePermissionItem] = []

    model_config = ConfigDict(from_attributes=True)
