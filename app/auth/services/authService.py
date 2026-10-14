import logging
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.LMS.models.userModel import User
from app.auth.schemas.authSchema import LoginRequest, LoginResponse, LogoutResponse, UserTokenPayload
from app.core.security import (
    create_access_token,
    verify_employee_password
)

logger = logging.getLogger("ntf_backend.auth")


def authenticate_employee(db: Session, login_data: LoginRequest) -> LoginResponse:
    """
    Authenticate employee via email and password:
    1. Validates missing input fields (400 Bad Request).
    2. Fetches employee record by email from the database.
    3. Verifies account is active (is_active = 1, otherwise 403 Forbidden).
    4. Verifies password against stored password_hash including default DOB format parsing (401 Unauthorized).
    5. Returns signed JWT token with user identity and role payload (id, username, email, role).
    """
    # 1. Credentials & Missing Input Validation: Only Email and Password
    raw_email = login_data.email
    raw_password = login_data.password

    if not raw_email or not str(raw_email).strip() or not raw_password or not str(raw_password).strip():
        logger.warning("Authentication failed: Missing email or password in request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required."
        )

    email = str(raw_email).strip()
    password = str(raw_password).strip()

    # 2. Fetch employee record from database by email (case-insensitive)
    # (also checks payCode as fallback if employee code is passed in email field)
    user = db.query(User).filter(
        (func.lower(User.email) == email.lower()) |
        (User.payCode == email)
    ).first()

    if not user:
        logger.warning(f"Authentication failed: No user found for email '{email}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # 3. Check account active status (ensure account is active: is_active = 1)
    is_active = getattr(user, "is_active", None)
    if is_active is None:
        is_active = getattr(user, "active", True)

    if not is_active:
        logger.warning(f"Authentication denied: User ID {user.id} ('{email}') is deactivated (is_active = 0)")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact your administrator."
        )

    # 4. Verify password against stored password_hash + DOB format parsing/matching
    stored_hash = user.passwordHash
    is_valid_pwd = verify_employee_password(
        plain_password=password,
        stored_hash=stored_hash,
        employee_dob=user.dob
    )

    if not is_valid_pwd:
        logger.warning(f"Authentication failed: Invalid password for user ID {user.id} ('{email}')")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # 5. Generate signed JWT token with user identity and role payload (id, username, email, role)
    canonical_username = user.payCode or user.empName or (user.email.split("@")[0] if user.email else str(user.id))
    canonical_role = user.role or "OPERATOR"

    token_payload = {
        "sub": str(user.id),
        "id": user.id,
        "username": canonical_username,
        "email": user.email,
        "role": canonical_role
    }

    access_token = create_access_token(data=token_payload)

    logger.info(f"Authentication successful for user ID {user.id} ({canonical_username}), role '{canonical_role}'")

    user_payload = UserTokenPayload(
        id=user.id,
        username=canonical_username,
        email=user.email,
        role=canonical_role,
        empName=user.empName,
        payCode=user.payCode,
        active=bool(is_active)
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        token=access_token,
        user=user_payload
    )


def logout_employee() -> LogoutResponse:
    """
    Log out employee and return confirmation.
    Stateless JWT tokens are cleared client-side.
    """
    return LogoutResponse(
        status="success",
        message="Successfully logged out"
    )
