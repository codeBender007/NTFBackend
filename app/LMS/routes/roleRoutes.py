from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.LMS.models.userModel import User
from app.LMS.schemas.roleSchema import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleDetailResponse,
)
from app.LMS.services import roleService

router = APIRouter(
    prefix="/roles",
    tags=["LMS - Roles"]
)


@router.post(
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new role"
)
@router.post(
    "/",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def createRole(
    roleData: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new role. Requires administrative authorization."""
    return roleService.create_role(db=db, role_data=roleData)


@router.get(
    "",
    response_model=List[RoleResponse],
    summary="Get all roles"
)
@router.get(
    "/",
    response_model=List[RoleResponse],
    include_in_schema=False
)
def getRoles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all roles with pagination. Requires authentication."""
    return roleService.get_all_roles(db=db, skip=skip, limit=limit)


@router.get(
    "/{role_id}",
    response_model=RoleDetailResponse,
    summary="Get role details"
)
def getRole(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve detailed role information including assigned pages and permissions."""
    return roleService.get_role_details(db=db, role_id=role_id)


@router.put(
    "/{role_id}",
    response_model=RoleResponse,
    summary="Update role"
)
def updateRole(
    role_id: int,
    roleData: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update role name and settings. Requires administrative authorization."""
    return roleService.update_role(
        db=db,
        role_id=role_id,
        role_data=roleData,
        current_user=current_user
    )


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete role"
)
def deleteRole(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete role.
    Prevents deletion of Superadmin and roles currently assigned to active users.
    Requires administrative authorization.
    """
    roleService.delete_role(db=db, role_id=role_id, current_user=current_user)
    return {
        "message": f"Role ID {role_id} deleted successfully."
    }
