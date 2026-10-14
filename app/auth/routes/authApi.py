import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth.schemas.authSchema import LoginRequest, LoginResponse, LogoutResponse
from app.auth.services import authService

logger = logging.getLogger("ntf_backend.auth.api")

router = APIRouter()


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Employee Authentication / Login",
    description=(
        "Authenticates an employee using only email and password. "
        "Supports bcrypt-hashed passwords as well as Date of Birth (DOB) default passwords "
        "assigned during bulk Excel employee import in formats like YYYY-MM-DD, DD-MM-YYYY, DDMMYYYY, or DD/MM/YYYY."
    )
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Employee login endpoint.
    - Accepts strictly two credentials: email and password
    - Validates email and password presence (400)
    - Verifies employee account is active (403 if deactivated)
    - Validates credentials and verifies DOB default format matching (401 if invalid)
    - Generates and returns a signed JWT token containing id, username, email, and role
    """
    return authService.authenticate_employee(db=db, login_data=login_data)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Employee Logout",
    description="Terminates employee session and invalidates client credentials."
)
def logout():
    """
    Employee logout endpoint.
    Returns success status to confirm termination of the client session.
    """
    return authService.logout_employee()
