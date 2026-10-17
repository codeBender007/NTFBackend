from typing import List, Optional, Union
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import decode_access_token
from app.LMS.models.userModel import User

security_scheme = HTTPBearer(auto_error=False)

ADMIN_ROLES = {"SUPER_ADMIN", "SUPERADMIN", "SUPER ADMIN", "ADMIN", "ADMINISTRATOR"}
VALID_PERMISSION_ACTIONS = {"canView", "canCreate", "canEdit", "canDelete", "canUploadExcel"}


def get_current_user(
    request: Request,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Extracts and validates the JWT token from request context or Authorization header
    and retrieves the authenticated active employee.
    """
    # 1. Check if user payload was already verified and injected by AuthenticationMiddleware
    payload = getattr(request.state, "user", None) or request.scope.get("user")

    # 2. If not already decoded, decode from Authorization header
    if not payload:
        if not auth_credentials or not auth_credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access denied. Please log in first.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        payload = decode_access_token(auth_credentials.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access denied. Please log in first.",
                headers={"WWW-Authenticate": "Bearer"}
            )

    user_id = payload.get("id") or payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing user ID",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )

    is_active = getattr(user, "is_active", None)
    if is_active is None:
        is_active = getattr(user, "active", True)

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact your administrator."
        )

    return user


def require_role(allowed_roles: Union[str, List[str]]):
    """
    Dependency factory to enforce role-based access control by role name.
    """
    roles = [allowed_roles] if isinstance(allowed_roles, str) else allowed_roles
    normalized_allowed = {r.upper() for r in roles}

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (getattr(current_user, "role", "") or "").upper()
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {roles}"
            )
        return current_user

    return role_checker


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Enforce administrative authorization for management APIs.
    """
    user_role = (getattr(current_user, "role", "") or "").upper()
    if user_role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to perform this action."
        )
    return current_user


def require_permission(module: str, page_key: str, action: str):
    """
    Reusable permission-check dependency helper for fine-grained page permission enforcement.
    Usage:
        @router.post("/items", dependencies=[Depends(require_permission("LMS", "users", "canCreate"))])
    """
    if action not in VALID_PERMISSION_ACTIONS:
        raise ValueError(f"Invalid permission action: {action}. Must be one of {VALID_PERMISSION_ACTIONS}")

    def permission_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        user_role_str = (getattr(current_user, "role", "") or "").upper()

        # 1. Superadmin has full unrestricted system access
        if user_role_str in {"SUPER_ADMIN", "SUPERADMIN", "SUPER ADMIN"}:
            return current_user

        # 2. Check active user
        is_active = getattr(current_user, "is_active", None)
        if is_active is None:
            is_active = getattr(current_user, "active", True)
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated."
            )

        # 3. Resolve user role ID
        role_id = getattr(current_user, "roleId", None)
        if not role_id and current_user.role:
            from app.LMS.models.roleModel import Role
            role_rec = db.query(Role).filter(func.lower(Role.name) == func.lower(current_user.role)).first()
            if role_rec:
                role_id = role_rec.id

        if not role_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: User does not have an active role assigned."
            )

        # 4. Resolve target page
        from app.LMS.models.pageModel import Page
        pages = db.query(Page).filter(func.upper(Page.module) == module.upper()).all()
        target_page = None
        for p in pages:
            if p.pageKey.lower() == page_key.lower() or p.name.lower() == page_key.lower():
                target_page = p
                break

        if not target_page:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Page '{page_key}' in module '{module}' is not configured."
            )

        # 5. Check role permission record
        from app.LMS.models.rolePermissionModel import RolePermission
        perm = (
            db.query(RolePermission)
            .filter(RolePermission.roleId == role_id, RolePermission.pageId == target_page.id)
            .first()
        )

        if not perm or not getattr(perm, action, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: User lacks '{action}' permission on page '{target_page.name}'."
            )

        return current_user

    return permission_checker


__all__ = [
    "get_db",
    "get_current_user",
    "require_role",
    "require_admin",
    "require_permission",
]
