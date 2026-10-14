from typing import List, Optional, Union
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.LMS.models.userModel import User

security_scheme = HTTPBearer(auto_error=False)


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
    Dependency factory to enforce role-based access control.
    """
    roles = [allowed_roles] if isinstance(allowed_roles, str) else allowed_roles

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {roles}"
            )
        return current_user

    return role_checker


__all__ = ["get_db", "get_current_user", "require_role"]
