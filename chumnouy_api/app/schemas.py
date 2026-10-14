from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthRead(BaseModel):
    status: str
    service: str
    version: str
    environment: str


# --- Auth --------------------------------------------------------------------


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=120)
    workspace_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(APIModel):
    id: UUID
    email: EmailStr
    name: str
    is_verified: bool
    created_at: datetime


class WorkspaceRead(APIModel):
    id: UUID
    name: str
    slug: str
    role: str


class AuthRead(BaseModel):
    token: str
    user: UserRead
    workspace: WorkspaceRead


class MeRead(BaseModel):
    user: UserRead
    workspaces: list[WorkspaceRead]


# --- Integrations & keys -----------------------------------------------------


class IntegrationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] | None = None


class IntegrationRead(APIModel):
    id: UUID
    name: str
    slug: str
    scopes: list[str]
    is_active: bool
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    environment: Literal["test", "live"] = "live"
    scopes: list[str] | None = None


class ApiKeyRead(APIModel):
    id: UUID
    name: str
    key_prefix: str
    environment: str
    scopes: list[str]
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreated(BaseModel):
    """Returned once, at creation. ``key`` is never retrievable again."""

    key: str
    api_key: ApiKeyRead
