from typing import List, Union
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.LMS.models.userModel import User
from app.LMS.schemas.rolePermissionSchema import (
    SinglePagePermissionUpdate,
    BulkPagePermissionItem,
    RolePermissionPageResponse,
)
from app.LMS.services import rolePermissionService

router = APIRouter(
    prefix="/roles/{role_id}/permissions",
    tags=["LMS - Role Permissions"]
)


@router.get(
    "",
    response_model=List[RolePermissionPageResponse],
    summary="Get assigned page permissions for a role"
)
@router.get(
    "/",
    response_model=List[RolePermissionPageResponse],
    include_in_schema=False
)
def getRolePermissions(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all assigned pages and their 5 permissions for a specific role.
    Requires authentication.
    """
    return rolePermissionService.get_role_permissions(db=db, role_id=role_id)


@router.put(
    "",
    response_model=List[RolePermissionPageResponse],
    summary="Bulk save or update role permissions"
)
@router.put(
    "/",
    response_model=List[RolePermissionPageResponse],
    include_in_schema=False
)
def bulkUpdateRolePermissions(
    role_id: int,
    permissions: Union[List[BulkPagePermissionItem], dict] = Body(...),
    sync: bool = Query(False, description="If true, removes assignments for pages not in payload"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Bulk save or update a role's page permissions using an atomic transaction.
    Accepts a list of permissions: [{pageId, canView, canCreate, canEdit, canDelete, canUploadExcel}].
    Requires administrative authorization.
    """
    if isinstance(permissions, dict):
        raw_items = permissions.get("permissions", [])
        items = [BulkPagePermissionItem(**item) for item in raw_items]
    else:
        items = permissions

    return rolePermissionService.bulk_update_role_permissions(
        db=db,
        role_id=role_id,
        permissions_list=items,
        sync=sync
    )


@router.put(
    "/{page_id}",
    response_model=RolePermissionPageResponse,
    summary="Update single page permissions for a role"
)
def updateSinglePagePermission(
    role_id: int,
    page_id: int,
    perms: SinglePagePermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update or assign permissions for a single page on a specific role.
    Requires administrative authorization.
    """
    return rolePermissionService.update_single_page_permission(
        db=db,
        role_id=role_id,
        page_id=page_id,
        perms=perms
    )


@router.delete(
    "/{page_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove page permission assignment from role"
)
def deleteRolePermission(
    role_id: int,
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Remove page assignment and permissions from the role.
    Requires administrative authorization.
    """
    rolePermissionService.delete_page_permission(db=db, role_id=role_id, page_id=page_id)
    return {
        "message": f"Permissions for page ID {page_id} successfully removed from role ID {role_id}."
    }
