"""Persistence helpers for identity authentication use cases."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.identity.infrastructure.models import UserModel


class IdentityRepository:
    """Encapsulates user lookup queries used by authentication flows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active_users_by_email(self, email: str) -> list[UserModel]:
        statement: Select[tuple[UserModel]] = (
            select(UserModel)
            .where(
                UserModel.email == email,
                UserModel.is_active.is_(True),
            )
            .order_by(UserModel.created_at.asc(), UserModel.id.asc())
        )
        return list(self._session.scalars(statement))
