"""API schemas for proposal endpoints and bank callbacks."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SimulateProposalRequest(BaseModel):
    client_id: UUID
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    installments: int = Field(ge=1, le=120)


class ProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    client_id: UUID
    external_protocol: str | None
    type: str
    amount: Decimal
    installments: int
    interest_rate: Decimal | None
    installment_value: Decimal | None
    status: str
    bank_response: dict | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID


class ProposalListResponse(BaseModel):
    items: list[ProposalResponse]
    total: int
    page: int
    page_size: int


class ProposalAcceptedResponse(BaseModel):
    id: UUID
    status: str
    message: str
