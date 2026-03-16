"""Read use cases for the clients module."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.security import AuthenticatedUser
from app.modules.clients.domain.exceptions import ClientNotFoundError
from app.modules.clients.infrastructure.models import ClientModel
from app.modules.clients.infrastructure.repository import ClientRepository


@dataclass(frozen=True)
class ListClientsResult:
    items: list[ClientModel]
    total: int
    page: int
    page_size: int


class ClientQueries:
    """Coordinates tenant-scoped client reads."""

    def __init__(self, repository: ClientRepository) -> None:
        self._repository = repository

    def list(
        self,
        *,
        actor: AuthenticatedUser,
        page: int,
        page_size: int,
    ) -> ListClientsResult:
        items = self._repository.list_by_tenant(
            tenant_id=actor.tenant_id,
            page=page,
            page_size=page_size,
        )
        total = self._repository.count_by_tenant(tenant_id=actor.tenant_id)
        return ListClientsResult(items=items, total=total, page=page, page_size=page_size)

    def get_by_id(self, *, actor: AuthenticatedUser, client_id: UUID) -> ClientModel:
        client = self._repository.get_by_tenant_and_id(
            tenant_id=actor.tenant_id,
            client_id=client_id,
        )
        if client is None:
            raise ClientNotFoundError()

        return client
