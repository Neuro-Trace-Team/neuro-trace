from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.core.roles import Role


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=1024)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: Role = Role.DOCTOR


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    is_active: bool | None = None


class CurrentUserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    items: list[UserResponse]
    page: int
    page_size: int
    total: int
