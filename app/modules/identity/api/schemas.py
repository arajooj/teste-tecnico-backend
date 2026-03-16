"""API schemas for authentication endpoints."""

from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    tenant_id: UUID
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
