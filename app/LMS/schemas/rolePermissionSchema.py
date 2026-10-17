from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class PermissionFlags(BaseModel):
    canView: bool = False
    canCreate: bool = False
    canEdit: bool = False
    canDelete: bool = False
    canUploadExcel: bool = False


class SinglePagePermissionUpdate(PermissionFlags):
    pass


class BulkPagePermissionItem(PermissionFlags):
    pageId: int


class RolePermissionPageResponse(BaseModel):
    pageId: int
    module: str
    page: str
    pageKey: str
    canView: bool = False
    canCreate: bool = False
    canEdit: bool = False
    canDelete: bool = False
    canUploadExcel: bool = False

    model_config = ConfigDict(from_attributes=True)


class RolePermissionResponse(BaseModel):
    id: int
    roleId: int
    pageId: int
    canView: bool = False
    canCreate: bool = False
    canEdit: bool = False
    canDelete: bool = False
    canUploadExcel: bool = False

    model_config = ConfigDict(from_attributes=True)
