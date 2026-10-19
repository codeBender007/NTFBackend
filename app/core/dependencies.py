from typing import List, Optional, Union
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import decode_access_token
from app.LMS.models.userModel import User

security_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")

ADMIN_ROLES = {"SUPER_ADMIN", "SUPERADMIN", "SUPER ADMIN", "ADMIN", "ADMINISTRATOR"}
VALID_PERMISSION_ACTIONS = {"canView", "canCreate", "canEdit", "canDelete", "canUploadExcel"}


def get_current_user(
    request: Request,
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Extracts and validates the JWT token from request context, Authorization header,
    cookies, or alternative headers and retrieves the authenticated active employee.
    """
    # 1. Check if user payload was already verified and injected by AuthenticationMiddleware
    payload = getattr(request.state, "user", None) or request.scope.get("user")

    # 2. If not already decoded, decode from credentials, headers, or cookies
    if not payload:
        raw_token = None
        if auth_credentials and auth_credentials.credentials:
            raw_token = auth_credentials.credentials
        elif request.headers.get("authorization"):
            raw_token = request.headers.get("authorization")
        elif request.headers.get("Authorization"):
            raw_token = request.headers.get("Authorization")
        elif request.headers.get("x-access-token"):
            raw_token = request.headers.get("x-access-token")
        elif request.headers.get("x-auth-token"):
            raw_token = request.headers.get("x-auth-token")
        elif request.cookies.get("access_token"):
            raw_token = request.cookies.get("access_token")
        elif request.cookies.get("token"):
            raw_token = request.cookies.get("token")

        if not raw_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access denied. Please log in first.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        payload = decode_access_token(raw_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access denied. Please log in first.",
                headers={"WWW-Authenticate": "Bearer"}
            )

    raw_user_id = payload.get("id") or payload.get("userId") or payload.get("sub")
    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing user identifier",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = None
    if isinstance(raw_user_id, int) or (isinstance(raw_user_id, str) and raw_user_id.isdigit()):
        user = db.query(User).filter(User.id == int(raw_user_id)).first()
    elif isinstance(raw_user_id, str) and "@" in raw_user_id:
        user = db.query(User).filter(func.lower(User.email) == raw_user_id.strip().lower()).first()

    if not user and payload.get("email"):
        user = db.query(User).filter(func.lower(User.email) == payload.get("email").strip().lower()).first()

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
    normalized_allowed = {r.upper().replace("-", "_").replace(" ", "_").strip() for r in roles}

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        raw_role = getattr(current_user, "role", None)
        if not raw_role and getattr(current_user, "role_obj", None):
            raw_role = current_user.role_obj.name
        user_role = (raw_role or "").upper().replace("-", "_").replace(" ", "_").strip()
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
    raw_role = getattr(current_user, "role", None)
    if not raw_role and getattr(current_user, "role_obj", None):
        raw_role = current_user.role_obj.name
    normalized_role = (raw_role or "").upper().replace("-", "_").replace(" ", "_").strip()
    clean_role_no_sep = normalized_role.replace("_", "")

    if (
        normalized_role not in ADMIN_ROLES
        and clean_role_no_sep not in {"SUPERADMIN", "ADMIN", "ADMINISTRATOR"}
    ):
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
