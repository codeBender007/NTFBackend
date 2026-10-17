from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.LMS.models.userModel import User
from app.LMS.schemas.pageSchema import (
    PageCreate,
    PageUpdate,
    PageResponse,
)
from app.LMS.services import pageService

router = APIRouter(
    prefix="/pages",
    tags=["LMS - Pages"]
)


@router.post(
    "",
    response_model=PageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new page"
)
@router.post(
    "/",
    response_model=PageResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def createPage(
    pageData: PageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new page across DASHBOARD, LMS, or CMS modules.
    Requires administrative authorization.
    """
    return pageService.create_page(db=db, page_data=pageData)


@router.get(
    "",
    response_model=List[PageResponse],
    summary="Get all pages"
)
@router.get(
    "/",
    response_model=List[PageResponse],
    include_in_schema=False
)
def getPages(
    module: Optional[str] = Query(None, description="Filter by module (DASHBOARD, LMS, CMS)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all configured pages, optionally filtered by module. Requires authentication."""
    return pageService.get_all_pages(db=db, module=module, skip=skip, limit=limit)


@router.get(
    "/{page_id}",
    response_model=PageResponse,
    summary="Get page details"
)
def getPage(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve details for a specific page by ID. Requires authentication."""
    return pageService.get_page_by_id(db=db, page_id=page_id)


@router.put(
    "/{page_id}",
    response_model=PageResponse,
    summary="Update page"
)
def updatePage(
    page_id: int,
    pageData: PageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update page configuration. Requires administrative authorization."""
    return pageService.update_page(db=db, page_id=page_id, page_data=pageData)


@router.delete(
    "/{page_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete page"
)
def deletePage(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a page and its associated role permissions. Requires administrative authorization."""
    pageService.delete_page(db=db, page_id=page_id)
    return {
        "message": f"Page ID {page_id} deleted successfully."
    }
