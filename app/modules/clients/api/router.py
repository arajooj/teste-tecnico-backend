"""Client API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.modules.clients.api.schemas import ClientListResponse, ClientResponse, ClientWriteRequest
from app.modules.clients.application.commands import (
    ClientCommands,
    CreateClientCommand,
    UpdateClientCommand,
)
from app.modules.clients.application.queries import ClientQueries
from app.modules.clients.infrastructure.repository import ClientRepository

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientWriteRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ClientResponse:
    repository = ClientRepository(db)
    command_handler = ClientCommands(repository)
    client = command_handler.create(
        actor=current_user,
        command=CreateClientCommand(
            name=payload.name,
            cpf=payload.cpf,
            birth_date=payload.birth_date,
            phone=payload.phone,
        ),
    )
    return ClientResponse.model_validate(client)


@router.get("", response_model=ClientListResponse, status_code=status.HTTP_200_OK)
def list_clients(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ClientListResponse:
    repository = ClientRepository(db)
    query_handler = ClientQueries(repository)
    result = query_handler.list(actor=current_user, page=page, page_size=page_size)
    return ClientListResponse(
        items=[ClientResponse.model_validate(client) for client in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{client_id}", response_model=ClientResponse, status_code=status.HTTP_200_OK)
def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ClientResponse:
    repository = ClientRepository(db)
    query_handler = ClientQueries(repository)
    client = query_handler.get_by_id(actor=current_user, client_id=client_id)
    return ClientResponse.model_validate(client)


@router.put("/{client_id}", response_model=ClientResponse, status_code=status.HTTP_200_OK)
def update_client(
    client_id: UUID,
    payload: ClientWriteRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ClientResponse:
    repository = ClientRepository(db)
    command_handler = ClientCommands(repository)
    client = command_handler.update(
        actor=current_user,
        command=UpdateClientCommand(
            client_id=client_id,
            name=payload.name,
            cpf=payload.cpf,
            birth_date=payload.birth_date,
            phone=payload.phone,
        ),
    )
    return ClientResponse.model_validate(client)
