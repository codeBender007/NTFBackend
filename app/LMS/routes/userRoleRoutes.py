from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.LMS.models.userModel import User
from app.LMS.schemas.userRoleSchema import (
    AssignUserRoleRequest,
    AssignUserRoleResponse,
    UserEffectivePermissionsResponse,
)
from app.LMS.services import userRoleService

router = APIRouter(
    tags=["LMS - User Roles & Permissions"]
)


@router.put(
    "/users/{user_id}/role",
    response_model=AssignUserRoleResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign or change a user's role"
)
def assignUserRole(
    user_id: int,
    payload: AssignUserRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Assign or change a user's role.
    Requires administrative authorization.
    Prevents self-elevation and unauthorized Superadmin assignment.
    """
    return userRoleService.assign_user_role(
        db=db,
        user_id=user_id,
        role_id=payload.roleId,
        current_user=current_user
    )


@router.get(
    "/users/{user_id}/permissions",
    response_model=UserEffectivePermissionsResponse,
    summary="Get effective permissions of a specific user"
)
def getUserPermissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get the effective role, assigned pages, and permissions for a specific user.
    Requires administrative authorization.
    """
    return userRoleService.get_user_effective_permissions(db=db, user_id=user_id)


@router.get(
    "/me/permissions",
    response_model=UserEffectivePermissionsResponse,
    summary="Get current authenticated user's permissions"
)
def getMyPermissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the currently authenticated user's active role, assigned pages, and permissions.
    Requires standard user authentication.
    """
    return userRoleService.get_me_effective_permissions(db=db, current_user=current_user)
