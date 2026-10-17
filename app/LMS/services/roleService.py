import logging
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.LMS.models.roleModel import Role
from app.LMS.models.pageModel import Page
from app.LMS.models.rolePermissionModel import RolePermission
from app.LMS.models.userModel import User
from app.LMS.schemas.roleSchema import RoleCreate, RoleUpdate

logger = logging.getLogger("ntf_backend.role_service")

SUPER_ADMIN_ROLE_NAMES = {"SUPER_ADMIN", "SUPERADMIN", "SUPER ADMIN"}


def get_all_roles(db: Session, skip: int = 0, limit: int = 100) -> List[Role]:
    """Retrieve all roles."""
    return db.query(Role).order_by(Role.id.asc()).offset(skip).limit(limit).all()


def get_role_by_id(db: Session, role_id: int) -> Role:
    """Retrieve a single role by its primary key ID."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found."
        )
    return role


def get_role_details(db: Session, role_id: int) -> Dict[str, Any]:
    """Retrieve role details including assigned pages and permissions."""
    role = get_role_by_id(db, role_id)

    # Query assigned permissions joined with page entities
    perms = (
        db.query(RolePermission, Page)
        .join(Page, RolePermission.pageId == Page.id)
        .filter(RolePermission.roleId == role_id)
        .order_by(Page.module.asc(), Page.name.asc())
        .all()
    )

    perm_list = []
    for rp, p in perms:
        perm_list.append({
            "pageId": p.id,
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
        "id": role.id,
        "name": role.name,
        "isActive": True,
        "permissions": perm_list
    }


def create_role(db: Session, role_data: RoleCreate) -> Role:
    """Create a new role with unique name validation."""
    clean_name = (role_data.name or "").strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role name cannot be empty."
        )

    # Check for existing role with same name (case-insensitive)
    existing = db.query(Role).filter(func.lower(Role.name) == clean_name.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with name '{clean_name}' already exists."
        )

    new_role = Role(name=clean_name)
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    logger.info(f"Role '{new_role.name}' created with ID {new_role.id}")
    return new_role


def update_role(db: Session, role_id: int, role_data: RoleUpdate, current_user: Optional[User] = None) -> Role:
    """Update role details with duplicate name protection and Superadmin safeguards."""
    role = get_role_by_id(db, role_id)

    # Protect Superadmin role from unauthorized modification
    is_superadmin_role = role.name.upper() in SUPER_ADMIN_ROLE_NAMES
    if is_superadmin_role and role_data.name:
        if role_data.name.strip().upper() not in SUPER_ADMIN_ROLE_NAMES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The Superadmin role name cannot be modified."
            )

    if role_data.name:
        clean_name = role_data.name.strip()
        if not clean_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role name cannot be empty."
            )

        # Check for duplicates excluding current role
        duplicate = (
            db.query(Role)
            .filter(func.lower(Role.name) == clean_name.lower(), Role.id != role_id)
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Another role with name '{clean_name}' already exists."
            )

        role.name = clean_name

    db.commit()
    db.refresh(role)
    logger.info(f"Role ID {role_id} updated: name='{role.name}'")
    return role


def delete_role(db: Session, role_id: int, current_user: Optional[User] = None) -> None:
    """
    Delete role.
    - Prevents deletion of the Superadmin role.
    - Prevents deletion if the role is currently assigned to users (returns 409 Conflict).
    """
    role = get_role_by_id(db, role_id)

    # 1. Protect Superadmin role
    if role.name.upper() in SUPER_ADMIN_ROLE_NAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The Superadmin role is protected and cannot be deleted."
        )

    # 2. Check if role is assigned to users
    assigned_user = (
        db.query(User)
        .filter((User.roleId == role_id) | (func.lower(User.role) == func.lower(role.name)))
        .first()
    )
    if assigned_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete role '{role.name}' because it is currently assigned to users "
                f"(e.g., PayCode: {assigned_user.payCode}, Name: {assigned_user.empName}). "
                "Please reassign these users before deleting this role."
            )
        )

    # 3. Clean up associated role permissions first
    db.query(RolePermission).filter(RolePermission.roleId == role_id).delete(synchronize_session=False)

    # 4. Delete the role
    db.delete(role)
    db.commit()
    logger.info(f"Role ID {role_id} ('{role.name}') deleted successfully")
