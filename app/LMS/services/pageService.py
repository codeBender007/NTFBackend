import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.LMS.models.pageModel import Page
from app.LMS.models.rolePermissionModel import RolePermission
from app.LMS.schemas.pageSchema import PageCreate, PageUpdate, VALID_MODULES

logger = logging.getLogger("ntf_backend.page_service")


def get_all_pages(db: Session, module: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Page]:
    """Retrieve all pages, optionally filtered by module."""
    query = db.query(Page)
    if module:
        clean_module = module.strip().upper()
        if clean_module not in VALID_MODULES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid module filter '{module}'. Must be one of: {', '.join(sorted(VALID_MODULES))}"
            )
        query = query.filter(func.upper(Page.module) == clean_module)

    return query.order_by(Page.module.asc(), Page.id.asc()).offset(skip).limit(limit).all()


def get_page_by_id(db: Session, page_id: int) -> Page:
    """Retrieve a single page by its primary key ID."""
    page = db.query(Page).filter(Page.id == page_id).first()
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page with ID {page_id} not found."
        )
    return page


def create_page(db: Session, page_data: PageCreate) -> Page:
    """
    Create a new page.
    Validates module and uniqueness of (module, name).
    """
    clean_module = page_data.module.strip().upper()
    clean_name = page_data.name.strip()

    if clean_module not in VALID_MODULES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Module must be one of: {', '.join(sorted(VALID_MODULES))}"
        )

    # Check for existing page in the same module with same name
    duplicate = (
        db.query(Page)
        .filter(
            func.upper(Page.module) == clean_module,
            func.lower(Page.name) == clean_name.lower()
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page '{clean_name}' already exists in module '{clean_module}'."
        )

    new_page = Page(module=clean_module, name=clean_name)
    db.add(new_page)
    db.commit()
    db.refresh(new_page)
    logger.info(f"Page '{new_page.name}' ({new_page.module}) created with ID {new_page.id}")
    return new_page


def update_page(db: Session, page_id: int, page_data: PageUpdate) -> Page:
    """Update page details with duplicate name/module protection."""
    page = get_page_by_id(db, page_id)

    target_module = page_data.module.strip().upper() if page_data.module else page.module
    target_name = page_data.name.strip() if page_data.name else page.name

    if target_module not in VALID_MODULES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Module must be one of: {', '.join(sorted(VALID_MODULES))}"
        )

    # Check for conflict if module or name changed
    if target_module != page.module or target_name.lower() != page.name.lower():
        duplicate = (
            db.query(Page)
            .filter(
                func.upper(Page.module) == target_module,
                func.lower(Page.name) == target_name.lower(),
                Page.id != page_id
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Page '{target_name}' already exists in module '{target_module}'."
            )

    page.module = target_module
    page.name = target_name

    db.commit()
    db.refresh(page)
    logger.info(f"Page ID {page_id} updated: module='{page.module}', name='{page.name}'")
    return page


def delete_page(db: Session, page_id: int) -> None:
    """Delete a page and its associated permissions."""
    page = get_page_by_id(db, page_id)

    # Clean up associated role permissions
    db.query(RolePermission).filter(RolePermission.pageId == page_id).delete(synchronize_session=False)

    db.delete(page)
    db.commit()
    logger.info(f"Page ID {page_id} ('{page.name}') deleted successfully")
