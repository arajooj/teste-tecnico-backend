"""Proposal persistence models."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProposalType(StrEnum):
    SIMULATION = "simulacao"
    PROPOSAL = "proposta"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SIMULATED = "simulated"
    SIMULATION_FAILED = "simulation_failed"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ProposalJobAction(StrEnum):
    SIMULATE = "simulate"
    SUBMIT = "submit"


class ProposalJobStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProposalModel(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        UniqueConstraint("simulation_protocol", name="uq_proposals_simulation_protocol"),
        UniqueConstraint("inclusion_protocol", name="uq_proposals_inclusion_protocol"),
        UniqueConstraint(
            "simulation_callback_token",
            name="uq_proposals_simulation_callback_token",
        ),
        UniqueConstraint(
            "inclusion_callback_token",
            name="uq_proposals_inclusion_callback_token",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    external_protocol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    simulation_protocol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inclusion_protocol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    simulation_callback_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inclusion_callback_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    installments: Mapped[int] = mapped_column(Integer, nullable=False)
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    installment_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ProposalStatus.PENDING.value,
    )
    bank_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processing_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_enqueued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_bank_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )


class ProposalJobModel(Base):
    __tablename__ = "proposal_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ProposalJobStatus.PENDING.value,
        server_default=ProposalJobStatus.PENDING.value,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
