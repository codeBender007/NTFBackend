import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.LMS.models.roleModel import Role
from app.LMS.models.pageModel import Page
from app.LMS.models.rolePermissionModel import RolePermission
from app.LMS.schemas.rolePermissionSchema import (
    SinglePagePermissionUpdate,
    BulkPagePermissionItem,
)

logger = logging.getLogger("ntf_backend.permission_service")


def _get_role_or_404(db: Session, role_id: int) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found."
        )
    return role


def _get_page_or_404(db: Session, page_id: int) -> Page:
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page with ID {page_id} not found."
        )
    return page


def get_role_permissions(db: Session, role_id: int) -> List[Dict[str, Any]]:
    """Get all assigned pages and their 5 permissions for a role."""
    _get_role_or_404(db, role_id)

    records = (
        db.query(RolePermission, Page)
        .join(Page, RolePermission.pageId == Page.id)
        .filter(RolePermission.roleId == role_id)
        .order_by(Page.module.asc(), Page.name.asc())
        .all()
    )

    result = []
    for rp, p in records:
        result.append({
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

    return result


def update_single_page_permission(
    db: Session,
    role_id: int,
    page_id: int,
    perms: SinglePagePermissionUpdate
) -> Dict[str, Any]:
    """
    Update or create permissions for a single page for a role (Upsert logic).
    """
    _get_role_or_404(db, role_id)
    page = _get_page_or_404(db, page_id)

    perm_record = (
        db.query(RolePermission)
        .filter(RolePermission.roleId == role_id, RolePermission.pageId == page_id)
        .first()
    )

    if not perm_record:
        perm_record = RolePermission(
            roleId=role_id,
            pageId=page_id,
            canView=bool(perms.canView),
            canCreate=bool(perms.canCreate),
            canEdit=bool(perms.canEdit),
            canDelete=bool(perms.canDelete),
            canUploadExcel=bool(perms.canUploadExcel),
        )
        db.add(perm_record)
    else:
        perm_record.canView = bool(perms.canView)
        perm_record.canCreate = bool(perms.canCreate)
        perm_record.canEdit = bool(perms.canEdit)
        perm_record.canDelete = bool(perms.canDelete)
        perm_record.canUploadExcel = bool(perms.canUploadExcel)

    db.commit()
    db.refresh(perm_record)
    logger.info(f"Updated permissions for role ID {role_id} on page ID {page_id}")

    return {
        "pageId": page.id,
        "module": page.module,
        "page": page.name,
        "pageKey": page.pageKey,
        "canView": bool(perm_record.canView),
        "canCreate": bool(perm_record.canCreate),
        "canEdit": bool(perm_record.canEdit),
        "canDelete": bool(perm_record.canDelete),
        "canUploadExcel": bool(perm_record.canUploadExcel),
    }


def bulk_update_role_permissions(
    db: Session,
    role_id: int,
    permissions_list: List[BulkPagePermissionItem],
    sync: bool = False
) -> List[Dict[str, Any]]:
    """
    Bulk save or update a role's page permissions using an atomic database transaction.
    - Each role/page combination is upserted.
    - If sync=True, assignments not included in the payload are removed for this role.
    - Other roles' permissions are NEVER modified.
    """
    _get_role_or_404(db, role_id)

    # Validate all page IDs upfront
    page_ids = [item.pageId for item in permissions_list]
    if page_ids:
        existing_pages = db.query(Page.id).filter(Page.id.in_(page_ids)).all()
        existing_page_ids = {p[0] for p in existing_pages}
        missing_ids = [pid for pid in page_ids if pid not in existing_page_ids]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"The following page IDs do not exist: {missing_ids}"
            )

    try:
        # Atomic transaction
        if sync and page_ids:
            # Remove permissions not in the incoming payload for this specific role only
            db.query(RolePermission).filter(
                RolePermission.roleId == role_id,
                ~RolePermission.pageId.in_(page_ids)
            ).delete(synchronize_session=False)
        elif sync and not page_ids:
            # Empty list with sync removes all permissions for this role
            db.query(RolePermission).filter(
                RolePermission.roleId == role_id
            ).delete(synchronize_session=False)

        # Upsert each permission record
        for item in permissions_list:
            perm_record = (
                db.query(RolePermission)
                .filter(RolePermission.roleId == role_id, RolePermission.pageId == item.pageId)
                .first()
            )
            if perm_record:
                perm_record.canView = bool(item.canView)
                perm_record.canCreate = bool(item.canCreate)
                perm_record.canEdit = bool(item.canEdit)
                perm_record.canDelete = bool(item.canDelete)
                perm_record.canUploadExcel = bool(item.canUploadExcel)
            else:
                perm_record = RolePermission(
                    roleId=role_id,
                    pageId=item.pageId,
                    canView=bool(item.canView),
                    canCreate=bool(item.canCreate),
                    canEdit=bool(item.canEdit),
                    canDelete=bool(item.canDelete),
                    canUploadExcel=bool(item.canUploadExcel),
                )
                db.add(perm_record)

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(f"Failed to bulk update permissions for role ID {role_id}: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update permissions due to a database transaction error."
        )

    return get_role_permissions(db, role_id)


def delete_page_permission(db: Session, role_id: int, page_id: int) -> None:
    """Remove page assignment and permissions from a role."""
    _get_role_or_404(db, role_id)
    _get_page_or_404(db, page_id)

    perm_record = (
        db.query(RolePermission)
        .filter(RolePermission.roleId == role_id, RolePermission.pageId == page_id)
        .first()
    )

    if not perm_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No permissions assigned for role ID {role_id} on page ID {page_id}."
        )

    db.delete(perm_record)
    db.commit()
    logger.info(f"Removed page ID {page_id} permissions from role ID {role_id}")
