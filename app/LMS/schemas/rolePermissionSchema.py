from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


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
    id: int = Field(..., description="Unique Page ID")
    pageId: int = Field(..., description="Unique Page ID (synonym for id)")
    module: str = Field(..., description="Module name: DASHBOARD, LMS, CMS", examples=["LMS"])
    name: str = Field(..., description="Page display name", examples=["Users"])
    page: str = Field(..., description="Page display name (synonym for name)", examples=["Users"])
    pageKey: str = Field(..., description="Frontend route identifier slug", examples=["users"])
    canView: bool = Field(False, description="View / Read permission flag")
    canCreate: bool = Field(False, description="Create new entity permission flag")
    canEdit: bool = Field(False, description="Edit / Update entity permission flag")
    canDelete: bool = Field(False, description="Delete entity permission flag")
    canUploadExcel: bool = Field(False, description="Bulk Excel upload permission flag")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "pageId": 1,
                "module": "LMS",
                "name": "Users",
                "page": "Users",
                "pageKey": "users",
                "canView": True,
                "canCreate": True,
                "canEdit": True,
                "canDelete": False,
                "canUploadExcel": True
            }
        }
    )


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
