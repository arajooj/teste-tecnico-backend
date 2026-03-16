"""Persistence helpers for tenant-scoped client operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.clients.infrastructure.models import ClientModel


class ClientRepository:
    """Encapsulates tenant-scoped client persistence queries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_tenant_and_id(self, *, tenant_id: UUID, client_id: UUID) -> ClientModel | None:
        statement: Select[tuple[ClientModel]] = select(ClientModel).where(
            ClientModel.tenant_id == tenant_id,
            ClientModel.id == client_id,
        )
        return self._session.scalar(statement)

    def get_by_tenant_and_cpf(self, *, tenant_id: UUID, cpf: str) -> ClientModel | None:
        statement: Select[tuple[ClientModel]] = select(ClientModel).where(
            ClientModel.tenant_id == tenant_id,
            ClientModel.cpf == cpf,
        )
        return self._session.scalar(statement)

    def list_by_tenant(
        self,
        *,
        tenant_id: UUID,
        page: int,
        page_size: int,
    ) -> list[ClientModel]:
        offset = (page - 1) * page_size
        statement: Select[tuple[ClientModel]] = (
            select(ClientModel)
            .where(ClientModel.tenant_id == tenant_id)
            .order_by(ClientModel.created_at.desc(), ClientModel.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(self._session.scalars(statement))

    def count_by_tenant(self, *, tenant_id: UUID) -> int:
        statement = select(func.count()).select_from(ClientModel).where(
            ClientModel.tenant_id == tenant_id
        )
        return int(self._session.scalar(statement) or 0)

    def add(self, client: ClientModel) -> ClientModel:
        self._session.add(client)
        self._session.commit()
        self._session.refresh(client)
        return client

    def save(self, client: ClientModel) -> ClientModel:
        self._session.add(client)
        self._session.commit()
        self._session.refresh(client)
        return client
