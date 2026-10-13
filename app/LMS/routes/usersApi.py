
from datetime import date
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Query
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.LMS.schemas.userSchema import (
    UserCreate,
    UserUpdate,
    UserResponse,
    ExcelUploadResponse
)
from app.LMS.services import userService


router = APIRouter(
    prefix="/users",
    tags=["LMS - Users"]
)


# 1. Get All Users with Filters
@router.get("/", response_model=List[UserResponse])
def getUsers(
    plantId: Optional[int] = Query(None),
    departmentId: Optional[int] = Query(None),
    subDepartmentId: Optional[int] = Query(None),
    lineId: Optional[int] = Query(None),
    machineId: Optional[int] = Query(None),
    shift: Optional[str] = Query(None),

    # Date of Joining Range
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),

    skillLevel: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),

    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),

    db: Session = Depends(get_db)
):
    # Validate Date Range
    if startDate and endDate and startDate > endDate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="startDate cannot be greater than endDate"
        )

    return userService.getAllUsers(
        db=db,
        plantId=plantId,
        departmentId=departmentId,
        subDepartmentId=subDepartmentId,
        lineId=lineId,
        machineId=machineId,
        shift=shift,
        startDate=startDate,
        endDate=endDate,
        skillLevel=skillLevel,
        active=active,
        skip=skip,
        limit=limit
    )


# 2. Get Single User by ID
@router.get("/{userId}", response_model=UserResponse)
def getUser(
    userId: int,
    db: Session = Depends(get_db)
):
    user = userService.getUserById(db, userId)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


# 3. Create User Manually
@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def createUser(
    userData: UserCreate,
    db: Session = Depends(get_db)
):
    return userService.createUser(db, userData)


# 4. Update User
@router.put("/{userId}", response_model=UserResponse)
def updateUser(
    userId: int,
    userData: UserUpdate,
    db: Session = Depends(get_db)
):
    user = userService.updateUser(db, userId, userData)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


# 5. Delete User (Soft Delete)
@router.delete(
    "/{userId}",
    status_code=status.HTTP_200_OK
)
def deleteUser(
    userId: int,
    db: Session = Depends(get_db)
):
    user = userService.deleteUser(db, userId)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {
        "message": "User deactivated successfully"
    }


# 6. Excel Bulk Upload
@router.post(
    "/upload-excel",
    response_model=ExcelUploadResponse,
    status_code=status.HTTP_201_CREATED
)
async def uploadUsersExcel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    filename = (file.filename or "").lower()

    if not filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Excel (.xlsx/.xls) or CSV files are supported"
        )

    return await userService.processExcelUpload(db, file)
