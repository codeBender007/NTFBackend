import logging
import re
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.LMS.models.roleModel import Role
from app.LMS.models.userModel import User
from app.auth.schemas.authSchema import LoginRequest, LoginResponse, LogoutResponse, UserTokenPayload
from app.core.security import (
    create_access_token,
    verify_employee_password
)

logger = logging.getLogger("ntf_backend.auth")

ADMIN_ROLE_TOKENS = {"SUPER_ADMIN", "SUPERADMIN", "ADMIN", "ADMINISTRATOR"}
SUPERVISOR_ROLE_TOKENS = {"SUPERVISOR", "LINE_SUPERVISOR", "SHIFT_SUPERVISOR"}
OPERATOR_ROLE_TOKENS = {"OPERATOR", "EMPLOYEE", "TRAINEE", "WORKER", "HELPER", "ASSEMBLER"}


def _normalize_role_token(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[\s\-]+", "_", str(value).strip()).upper()


def _resolve_user_role(db: Session, user: User) -> Tuple[Optional[int], str, str, str, bool, bool, bool]:
    """
    Resolve authoritative role metadata for role-based routing:
    Returns (role_id, role_name, canonical_role, role_type, is_admin, is_supervisor, is_employee).
    """
    role_id = getattr(user, "roleId", None)
    role_obj = getattr(user, "role_obj", None)
    if role_obj is None and role_id is not None:
        role_obj = db.query(Role).filter(Role.id == role_id).first()

    raw_role_name = (role_obj.name.strip() if role_obj and role_obj.name else None) or (
        user.role.strip() if user.role else None
    )

    # If roleId is missing on User but role string matches an entry in roles table, resolve roleId too
    if role_id is None and raw_role_name:
        matched_role = db.query(Role).filter(func.lower(Role.name) == raw_role_name.lower()).first()
        if matched_role:
            role_id = matched_role.id
            raw_role_name = matched_role.name

    role_name = raw_role_name or "OPERATOR"
    norm_role = _normalize_role_token(role_name)
    norm_desig = _normalize_role_token(getattr(user, "designation", None))

    # Determine role classification for Admin / Supervisor / Operator portals
    is_admin = norm_role in ADMIN_ROLE_TOKENS or norm_role.replace("_", "") in {"SUPERADMIN", "ADMIN", "ADMINISTRATOR"}
    is_supervisor = (not is_admin) and (
        norm_role in SUPERVISOR_ROLE_TOKENS
        or "SUPERVISOR" in norm_role
        or (norm_role in {"", "OPERATOR"} and "SUPERVISOR" in norm_desig)
    )
    is_employee = (not is_admin) and (not is_supervisor) and (
        norm_role in OPERATOR_ROLE_TOKENS or norm_desig in OPERATOR_ROLE_TOKENS
    )

    if is_admin:
        role_type = "ADMIN"
        canonical_role = norm_role if norm_role in ADMIN_ROLE_TOKENS else "ADMIN"
    elif is_supervisor:
        role_type = "SUPERVISOR"
        canonical_role = "SUPERVISOR"
    elif is_employee:
        role_type = "OPERATOR"
        canonical_role = "OPERATOR"
    else:
        # Custom management/staff roles (e.g. Line Leader, QA Manager) keep their role name
        role_type = "ADMIN"
        canonical_role = role_name

    return role_id, role_name, canonical_role, role_type, is_admin, is_supervisor, is_employee


def authenticate_employee(db: Session, login_data: LoginRequest) -> LoginResponse:
    """
    Role-aware authentication for Admins, Supervisors, and Operators/Employees:
    1. Validates missing input fields (400 Bad Request).
    2. Looks up matching account(s) by email/username, payCode, or trimmed empName (case-insensitive).
       When multiple employees share the exact same empName, matches the one whose password verifies.
    3. Verifies account is active (is_active = 1, otherwise 403 Forbidden).
    4. Verifies password against stored passwordHash (custom password, payCode hash, or legacy DOB).
    5. Returns signed JWT token + resolved role metadata + full hierarchy metadata.
    """
    raw_email = login_data.email
    raw_password = login_data.password

    if not raw_email or not str(raw_email).strip() or not raw_password or not str(raw_password).strip():
        logger.warning("Authentication failed: Missing email or password in request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required."
        )

    identifier = str(raw_email).strip()
    identifier_lower = identifier.lower()
    password = str(raw_password).strip()

    # 2. Fetch candidate employee records matching email/username, payCode, or trimmed empName
    candidates = (
        db.query(User)
        .options(joinedload(User.role_obj))
        .filter(
            (func.lower(User.email) == identifier_lower)
            | (User.payCode == identifier)
            | (func.lower(User.empName) == identifier_lower)
        )
        .order_by(User.id.asc())
        .all()
    )

    if not candidates:
        logger.warning(f"Authentication failed: No user found for email '{identifier}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Prioritize exact email or payCode match first, then empName matches
    def _candidate_priority(u: User) -> int:
        if u.email and u.email.strip().lower() == identifier_lower:
            return 0
        if u.payCode and u.payCode.strip() == identifier:
            return 1
        return 2

    candidates.sort(key=_candidate_priority)

    matched_user: Optional[User] = None
    matched_inactive_user: Optional[User] = None

    for cand in candidates:
        is_active_cand = getattr(cand, "is_active", None)
        if is_active_cand is None:
            is_active_cand = getattr(cand, "active", True)

        if verify_employee_password(
            plain_password=password,
            stored_hash=cand.passwordHash,
            employee_dob=cand.dob,
            employee_paycode=cand.payCode,
        ):
            if is_active_cand:
                matched_user = cand
                break
            if matched_inactive_user is None:
                matched_inactive_user = cand

    if matched_user is None:
        # Preserve exact 403 behavior for deactivated single-account or matched-inactive login
        if matched_inactive_user is not None:
            logger.warning(
                f"Authentication denied: User ID {matched_inactive_user.id} ('{identifier}') is deactivated (is_active = 0)"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Please contact your administrator."
            )
        # If there is a single candidate and it is deactivated, still return 403
        if len(candidates) == 1:
            only = candidates[0]
            only_active = getattr(only, "is_active", None)
            if only_active is None:
                only_active = getattr(only, "active", True)
            if not only_active:
                logger.warning(
                    f"Authentication denied: User ID {only.id} ('{identifier}') is deactivated (is_active = 0)"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is deactivated. Please contact your administrator."
                )
        logger.warning(f"Authentication failed: Invalid password for user ID {candidates[0].id} ('{identifier}')")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    user = matched_user
    is_active = getattr(user, "is_active", None)
    if is_active is None:
        is_active = getattr(user, "active", True)

    role_id, role_name, canonical_role, role_type, is_admin, is_supervisor, is_employee = (
        _resolve_user_role(db, user)
    )

    canonical_username = user.payCode or user.empName or (user.email.split("@")[0] if user.email else str(user.id))

    token_payload = {
        "sub": str(user.id),
        "id": user.id,
        "userId": user.id,
        "username": canonical_username,
        "email": user.email,
        "role": canonical_role,
        "roleId": role_id,
        "roleName": role_name,
        "roleType": role_type,
        "empName": user.empName,
        "payCode": user.payCode,
    }

    access_token = create_access_token(data=token_payload)

    logger.info(
        f"Authentication successful for user ID {user.id} ({canonical_username}), "
        f"role '{canonical_role}' (roleId={role_id}, roleType={role_type})"
    )

    user_payload = UserTokenPayload(
        id=user.id,
        userId=user.id,
        username=canonical_username,
        email=user.email,
        role=canonical_role,
        roleId=role_id,
        roleName=role_name,
        roleType=role_type,
        isAdmin=is_admin,
        isSupervisor=is_supervisor,
        isEmployee=is_employee,
        empName=user.empName,
        name=user.empName,
        payCode=user.payCode,
        cardNo=user.cardNo,
        designation=user.designation,
        shift=user.shift,
        dateOfJoining=user.dateOfJoining,
        joiningDate=user.dateOfJoining,
        plantId=user.plantId,
        plantLocation=user.plantLocation,
        departmentId=user.departmentId,
        departmentName=user.departmentName,
        subDepartmentId=user.subDepartmentId,
        subDepartmentName=user.subDepartmentName,
        lineId=user.lineId,
        lineName=user.lineName,
        machineId=user.machineId,
        machineName=user.machineName,
        active=bool(is_active),
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
