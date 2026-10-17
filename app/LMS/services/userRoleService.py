import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.LMS.models.userModel import User
from app.LMS.models.roleModel import Role
from app.LMS.models.pageModel import Page
from app.LMS.models.rolePermissionModel import RolePermission

logger = logging.getLogger("ntf_backend.user_role_service")

SUPER_ADMIN_ROLES = {"SUPER_ADMIN", "SUPERADMIN", "SUPER ADMIN"}


def assign_user_role(
    db: Session,
    user_id: int,
    role_id: int,
    current_user: User
) -> Dict[str, Any]:
    """
    Assign or change a user's role.
    - Prevents self-elevation / self-role modification.
    - Protects Superadmin assignment: only existing Superadmins can grant Superadmin.
    - Synchronizes both user.roleId (FK) and user.role (legacy string).
    """
    # 1. Self-assignment protection
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Users are not permitted to change or elevate their own role."
        )

    # 2. Retrieve user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )

    # 3. Retrieve target role
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found."
        )

    # 4. Superadmin elevation safeguard
    is_target_superadmin = role.name.upper() in SUPER_ADMIN_ROLES
    caller_role = (getattr(current_user, "role", "") or "").upper()
    if is_target_superadmin and caller_role not in SUPER_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Superadmin users can assign the Superadmin role."
        )

    # 5. Apply role assignment
    user.roleId = role.id
    user.role = role.name

    db.commit()
    db.refresh(user)

    logger.info(f"User ID {user_id} assigned role '{role.name}' (ID {role.id}) by User ID {current_user.id}")

    return {
        "userId": user.id,
        "empName": user.empName,
        "email": user.email,
        "roleId": user.roleId,
        "roleName": role.name,
        "message": f"Role '{role.name}' assigned successfully to {user.empName}."
    }


def get_user_effective_permissions(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Get the effective permissions for a specific user.
    - Return empty permissions if user is deactivated or has no valid role.
    - Superadmin users receive full access across active pages.
    - Standard roles receive their database-configured page permissions.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )

    # Inactive users have no effective permissions
    is_active = getattr(user, "is_active", None)
    if is_active is None:
        is_active = getattr(user, "active", True)
    if not is_active:
        return {
            "userId": user.id,
            "role": None,
            "permissions": []
        }

    # Resolve Role
    role = None
    if user.roleId:
        role = db.query(Role).filter(Role.id == user.roleId).first()

    # Fallback: if roleId not set, check legacy user.role string
    if not role and user.role:
        role = db.query(Role).filter(func.lower(Role.name) == func.lower(user.role)).first()
        if role:
            # Sync roleId
            user.roleId = role.id
            db.commit()

    if not role:
        return {
            "userId": user.id,
            "role": None,
            "permissions": []
        }

    # Handle Superadmin permissions
    if role.name.upper() in SUPER_ADMIN_ROLES or (user.role and user.role.upper() in SUPER_ADMIN_ROLES):
        all_pages = db.query(Page).order_by(Page.module.asc(), Page.name.asc()).all()
        # Overlay any custom configured permissions
        explicit_perms = {
            rp.pageId: rp
            for rp in db.query(RolePermission).filter(RolePermission.roleId == role.id).all()
        }
        permissions = []
        for p in all_pages:
            ep = explicit_perms.get(p.id)
            permissions.append({
                "module": p.module,
                "page": p.name,
                "pageKey": p.pageKey,
                "canView": ep.canView if ep else True,
                "canCreate": ep.canCreate if ep else True,
                "canEdit": ep.canEdit if ep else True,
                "canDelete": ep.canDelete if ep else True,
                "canUploadExcel": ep.canUploadExcel if ep else True,
            })
        return {
            "userId": user.id,
            "role": {
                "id": role.id,
                "name": role.name
            },
            "permissions": permissions
        }

    # Standard Role Permissions
    records = (
        db.query(RolePermission, Page)
        .join(Page, RolePermission.pageId == Page.id)
        .filter(RolePermission.roleId == role.id)
        .order_by(Page.module.asc(), Page.name.asc())
        .all()
    )

    permissions = []
    for rp, p in records:
        permissions.append({
            "module": p.module,
            "page": p.name,
            "pageKey": p.pageKey,
            "canView": bool(rp.canView),
            "canCreate": bool(rp.canCreate),
            "canEdit": bool(rp.canEdit),
            "canDelete": bool(rp.canDelete),
            "canUploadExcel": bool(rp.canUploadExcel),
        })

    return {
        "userId": user.id,
        "role": {
            "id": role.id,
            "name": role.name
        },
        "permissions": permissions
    }


def get_me_effective_permissions(db: Session, current_user: User) -> Dict[str, Any]:
    """Get the currently authenticated user's role, assigned pages, and permissions."""
    return get_user_effective_permissions(db, current_user.id)
