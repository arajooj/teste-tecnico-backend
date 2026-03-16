"""API schemas for client endpoints."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClientWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cpf: str = Field(min_length=11, max_length=11)
    birth_date: date
    phone: str = Field(min_length=8, max_length=20)


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    cpf: str
    birth_date: date
    phone: str
    created_at: datetime
    created_by: UUID


class ClientListResponse(BaseModel):
    items: list[ClientResponse]
    total: int
    page: int
    page_size: int
