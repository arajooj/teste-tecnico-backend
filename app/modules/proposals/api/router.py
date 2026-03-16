"""Proposal and bank webhook API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.modules.clients.infrastructure.repository import ClientRepository
from app.modules.proposals.api.schemas import (
    BankCallbackPayload,
    ProposalAcceptedResponse,
    ProposalListResponse,
    ProposalResponse,
    SimulateProposalRequest,
)
from app.modules.proposals.application.commands import (
    BankCallbackCommand,
    ProposalCommands,
    SimulateProposalCommand,
)
from app.modules.proposals.application.queries import ProposalQueries
from app.modules.proposals.infrastructure.queue import ProposalQueue
from app.modules.proposals.infrastructure.repository import ProposalRepository

router = APIRouter(prefix="/api/proposals", tags=["proposals"])
webhook_router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _build_commands(db: Session) -> ProposalCommands:
    proposal_repository = ProposalRepository(db)
    client_repository = ClientRepository(db)
    queue = ProposalQueue()
    return ProposalCommands(
        repository=proposal_repository,
        client_repository=client_repository,
        queue=queue,
    )


def _build_queries(db: Session) -> ProposalQueries:
    return ProposalQueries(ProposalRepository(db))


@router.post(
    "/simulate",
    response_model=ProposalAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def simulate_proposal(
    payload: SimulateProposalRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProposalAcceptedResponse:
    commands = _build_commands(db)
    proposal = commands.create_simulation(
        actor=current_user,
        command=SimulateProposalCommand(
            client_id=payload.client_id,
            amount=payload.amount,
            installments=payload.installments,
        ),
    )
    return ProposalAcceptedResponse(
        id=proposal.id,
        status=proposal.status,
        message="Proposal simulation queued successfully",
    )


@router.post(
    "/{proposal_id}/submit",
    response_model=ProposalAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_proposal(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProposalAcceptedResponse:
    commands = _build_commands(db)
    proposal = commands.submit(actor=current_user, proposal_id=proposal_id)
    return ProposalAcceptedResponse(
        id=proposal.id,
        status=proposal.status,
        message="Proposal submission queued successfully",
    )


@router.get("", response_model=ProposalListResponse, status_code=status.HTTP_200_OK)
def list_proposals(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    proposal_type: Annotated[str | None, Query(alias="type")] = None,
) -> ProposalListResponse:
    queries = _build_queries(db)
    result = queries.list(
        actor=current_user,
        page=page,
        page_size=page_size,
        status=status_filter,
        proposal_type=proposal_type,
    )
    return ProposalListResponse(
        items=[ProposalResponse.model_validate(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{proposal_id}", response_model=ProposalResponse, status_code=status.HTTP_200_OK)
def get_proposal(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProposalResponse:
    queries = _build_queries(db)
    proposal = queries.get_by_id(actor=current_user, proposal_id=proposal_id)
    return ProposalResponse.model_validate(proposal)


@webhook_router.post("/bank-callback", status_code=status.HTTP_204_NO_CONTENT)
def receive_bank_callback(payload: BankCallbackPayload, db: Session = Depends(get_db)) -> Response:
    commands = _build_commands(db)
    commands.handle_bank_callback(
        command=BankCallbackCommand(
            protocol=payload.protocol,
            event=payload.event,
            status=payload.status,
            data=payload.data,
            timestamp=payload.timestamp,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
