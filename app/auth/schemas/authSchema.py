from datetime import date
from typing import Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """
    Employee login request payload.
    Accepts username/email (or payCode) and password.
    """
    email: str = Field(
        ...,
        validation_alias=AliasChoices("email", "username"),
        description="Employee username, registered email, or payCode",
        examples=["employee@ntfauto.com", "Vishnu", "admin"]
    )
    password: str = Field(
        ...,
        description="Employee password (custom password, payCode default, or legacy DOB)",
        examples=["10144", "admin123", "01011990"]
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore"
    )


class UserTokenPayload(BaseModel):
    """
    Role-aware user identity and full hierarchy metadata included in login response.
    """
    id: int = Field(..., description="Unique employee identifier")
    userId: Optional[int] = Field(None, description="Alias of id for frontend compatibility")
    username: str = Field(..., description="Employee username or payCode")
    email: Optional[str] = Field(None, description="Employee email or login identifier")

    # Role-aware routing metadata (Admin, Supervisor, Operator/Employee)
    role: str = Field(..., description="Normalized routing role (e.g., SUPER_ADMIN, ADMIN, SUPERVISOR, OPERATOR)")
    roleId: Optional[int] = Field(None, description="Foreign key ID from roles master table")
    roleName: Optional[str] = Field(None, description="Resolved role name from roles table or user record")
    roleType: Optional[str] = Field(None, description="High-level portal role type: ADMIN, SUPERVISOR, or OPERATOR")
    isAdmin: bool = Field(False, description="True if user has Admin/Super Admin access")
    isSupervisor: bool = Field(False, description="True if user has Supervisor portal access")
    isEmployee: bool = Field(False, description="True if user has Operator/Employee portal access")

    # Employee profile & hierarchy metadata
    empName: Optional[str] = Field(None, description="Employee full name")
    name: Optional[str] = Field(None, description="Alias of empName")
    payCode: Optional[str] = Field(None, description="Employee payroll code")
    cardNo: Optional[str] = Field(None, description="Employee card number")
    designation: Optional[str] = Field(None, description="Employee designation")
    shift: Optional[str] = Field(None, description="Assigned shift")
    dateOfJoining: Optional[date] = Field(None, description="Employee joining date")
    joiningDate: Optional[date] = Field(None, description="Alias of dateOfJoining")

    plantId: Optional[int] = Field(None, description="Plant ID")
    plantLocation: Optional[str] = Field(None, description="Plant location / name")
    departmentId: Optional[int] = Field(None, description="Department ID")
    departmentName: Optional[str] = Field(None, description="Department name")
    subDepartmentId: Optional[int] = Field(None, description="Sub-department ID")
    subDepartmentName: Optional[str] = Field(None, description="Sub-department name")
    lineId: Optional[int] = Field(None, description="Line ID")
    lineName: Optional[str] = Field(None, description="Line name")
    machineId: Optional[int] = Field(None, description="Machine ID")
    machineName: Optional[str] = Field(None, description="Machine name")

    active: bool = Field(True, description="Account active status")

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    """
    Successful employee authentication response containing signed JWT and role-aware user identity.
    """
    access_token: str = Field(..., description="Signed JWT Bearer access token")
    token_type: str = Field("bearer", description="Token type")
    token: Optional[str] = Field(None, description="Alias for access_token for client compatibility")
    user: UserTokenPayload = Field(..., description="Authenticated employee details with role & hierarchy")

    def __init__(self, **data):
        if "access_token" in data and "token" not in data:
            data["token"] = data["access_token"]
        super().__init__(**data)


class TokenData(BaseModel):
    """
    Payload extracted from a verified JWT token.
    """
    id: Optional[int] = None
    userId: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    roleId: Optional[int] = None
    roleName: Optional[str] = None
    roleType: Optional[str] = None


class LogoutResponse(BaseModel):
    """
    Successful employee logout response.
    """
    status: str = Field("success", description="Status indicator")
    message: str = Field("Successfully logged out", description="Logout confirmation message")
