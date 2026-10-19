import re
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_MODULES = {"DASHBOARD", "LMS", "CMS"}


class PageBase(BaseModel):
    module: str = Field(
        ...,
        description="Module name under which the page belongs. Must be DASHBOARD, LMS, or CMS.",
        examples=["LMS", "DASHBOARD", "CMS"]
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Human-readable display name of the page (e.g., 'Users', 'Departments', 'Attendance Tracker').",
        examples=["Users", "Departments", "Attendance Tracker"]
    )
    pageKey: Optional[str] = Field(
        None,
        max_length=150,
        description=(
            "Unique frontend route slug / identifier used by UI navigation guards "
            "(e.g. 'users', 'departments', 'lms_roles', 'attendance_tracker'). "
            "If omitted, automatically slugified from name."
        ),
        examples=["users", "departments", "lms_roles", "attendance_tracker"]
    )
    isActive: Optional[bool] = Field(default=True, description="Active status")

    @field_validator("module")
    @classmethod
    def validate_module(cls, v: str) -> str:
        upper_v = (v or "").strip().upper()
        if upper_v not in VALID_MODULES:
            raise ValueError(f"Module must be one of: {', '.join(sorted(VALID_MODULES))}")
        return upper_v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = (v or "").strip()
        if not clean:
            raise ValueError("Page name cannot be empty")
        return clean

    @field_validator("pageKey")
    @classmethod
    def validate_page_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = re.sub(r'[^a-zA-Z0-9_]+', '_', v.strip().lower()).strip('_')
        if not clean:
            raise ValueError("pageKey must contain valid alphanumeric characters")
        return clean


class PageCreate(PageBase):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "module": "LMS",
                "name": "Users",
                "pageKey": "users",
                "isActive": True
            }
        }
    )


class PageUpdate(BaseModel):
    module: Optional[str] = Field(None, examples=["LMS"])
    name: Optional[str] = Field(None, examples=["User Management"])
    pageKey: Optional[str] = Field(None, examples=["users"])
    isActive: Optional[bool] = Field(None, examples=[True])

    @field_validator("module")
    @classmethod
    def validate_module(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        upper_v = v.strip().upper()
        if upper_v not in VALID_MODULES:
            raise ValueError(f"Module must be one of: {', '.join(sorted(VALID_MODULES))}")
        return upper_v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if not clean:
            raise ValueError("Page name cannot be empty")
        return clean

    @field_validator("pageKey")
    @classmethod
    def validate_page_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = re.sub(r'[^a-zA-Z0-9_]+', '_', v.strip().lower()).strip('_')
        if not clean:
            raise ValueError("pageKey must contain valid alphanumeric characters")
        return clean

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "module": "LMS",
                "name": "User Management",
                "pageKey": "users",
                "isActive": True
            }
        }
    )


class PageResponse(BaseModel):
    id: int = Field(..., description="Unique Page ID")
    module: str = Field(..., description="Module name: DASHBOARD, LMS, CMS")
    name: str = Field(..., description="Page display name")
    pageKey: str = Field(..., description="Unique frontend route slug / identifier")
    isActive: bool = True

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "module": "LMS",
                "name": "Users",
                "pageKey": "users",
                "isActive": True
            }
        }
    )
