from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """
    Employee login request payload.
    Accepts only two credentials: email and password.
    """
    email: str = Field(
        ...,
        description="Employee registered email address",
        examples=["employee@ntfauto.com"]
    )
    password: str = Field(
        ...,
        description="Employee password (supports standard password or Date of Birth DOB in formats like YYYY-MM-DD, DD-MM-YYYY, DDMMYYYY)",
        examples=["01011990", "1990-01-01"]
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore"
    )


class UserTokenPayload(BaseModel):
    """
    User identity and role summary included in token payload and response.
    """
    id: int = Field(..., description="Unique employee identifier")
    username: str = Field(..., description="Employee username or paycode")
    email: Optional[str] = Field(None, description="Employee email address")
    role: str = Field(..., description="Access control role (e.g., OPERATOR, SUPER_ADMIN)")
    empName: Optional[str] = Field(None, description="Employee full name")
    payCode: Optional[str] = Field(None, description="Employee payroll code")
    active: bool = Field(True, description="Account active status")

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    """
    Successful employee authentication response containing signed JWT and user identity.
    """
    access_token: str = Field(..., description="Signed JWT Bearer access token")
    token_type: str = Field("bearer", description="Token type")
    token: Optional[str] = Field(None, description="Alias for access_token for client compatibility")
    user: UserTokenPayload = Field(..., description="Authenticated employee details")

    def __init__(self, **data):
        if "access_token" in data and "token" not in data:
            data["token"] = data["access_token"]
        super().__init__(**data)


class TokenData(BaseModel):
    """
    Payload extracted from a verified JWT token.
    """
    id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class LogoutResponse(BaseModel):
    """
    Successful employee logout response.
    """
    status: str = Field("success", description="Status indicator")
    message: str = Field("Successfully logged out", description="Logout confirmation message")
