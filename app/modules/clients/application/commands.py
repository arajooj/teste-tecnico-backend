"""Write use cases for the clients module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.core.security import AuthenticatedUser
from app.modules.clients.domain.exceptions import (
    ClientAlreadyExistsError,
    ClientNotFoundError,
)
from app.modules.clients.infrastructure.models import ClientModel
from app.modules.clients.infrastructure.repository import ClientRepository


@dataclass(frozen=True)
class CreateClientCommand:
    name: str
    cpf: str
    birth_date: date
    phone: str


@dataclass(frozen=True)
class UpdateClientCommand:
    client_id: UUID
    name: str
    cpf: str
    birth_date: date
    phone: str


class ClientCommands:
    """Coordinates client writes while enforcing tenant isolation."""

    def __init__(self, repository: ClientRepository) -> None:
        self._repository = repository

    def create(self, *, actor: AuthenticatedUser, command: CreateClientCommand) -> ClientModel:
        existing_client = self._repository.get_by_tenant_and_cpf(
            tenant_id=actor.tenant_id,
            cpf=command.cpf,
        )
        if existing_client is not None:
            raise ClientAlreadyExistsError()

        client = ClientModel(
            tenant_id=actor.tenant_id,
            name=command.name,
            cpf=command.cpf,
            birth_date=command.birth_date,
            phone=command.phone,
            created_by=actor.user_id,
        )
        return self._repository.add(client)

    def update(self, *, actor: AuthenticatedUser, command: UpdateClientCommand) -> ClientModel:
        client = self._repository.get_by_tenant_and_id(
            tenant_id=actor.tenant_id,
            client_id=command.client_id,
        )
        if client is None:
            raise ClientNotFoundError()

        duplicated_client = self._repository.get_by_tenant_and_cpf(
            tenant_id=actor.tenant_id,
            cpf=command.cpf,
        )
        if duplicated_client is not None and duplicated_client.id != client.id:
            raise ClientAlreadyExistsError()

        client.name = command.name
        client.cpf = command.cpf
        client.birth_date = command.birth_date
        client.phone = command.phone
        return self._repository.save(client)
