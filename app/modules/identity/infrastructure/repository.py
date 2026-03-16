"""Persistence helpers for identity authentication use cases."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.identity.infrastructure.models import UserModel


class IdentityRepository:
    """Encapsulates user lookup queries used by authentication flows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_user_by_tenant_and_email(
        self,
        *,
        tenant_id: UUID,
        email: str,
    ) -> UserModel | None:
        statement: Select[tuple[UserModel]] = (
            select(UserModel)
            .where(
                UserModel.tenant_id == tenant_id,
                UserModel.email == email,
                UserModel.is_active.is_(True),
            )
        )
        return self._session.scalar(statement)
