from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_MODULES = {"DASHBOARD", "LMS", "CMS"}


class PageBase(BaseModel):
    module: str = Field(..., description="Module name: DASHBOARD, LMS, or CMS")
    name: str = Field(..., min_length=1, max_length=150, description="Display name of the page")
    pageKey: Optional[str] = Field(None, max_length=150, description="Unique identifier slug for the page")
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


class PageCreate(PageBase):
    pass


class PageUpdate(BaseModel):
    module: Optional[str] = None
    name: Optional[str] = None
    pageKey: Optional[str] = None
    isActive: Optional[bool] = None

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


class PageResponse(BaseModel):
    id: int
    module: str
    name: str
    pageKey: str
    isActive: bool = True

    model_config = ConfigDict(from_attributes=True)
