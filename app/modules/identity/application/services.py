"""Application services for identity authentication flows."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.exceptions import AppException
from app.core.security import create_access_token, verify_password
from app.modules.identity.infrastructure.models import UserModel
from app.modules.identity.infrastructure.repository import IdentityRepository


@dataclass(frozen=True)
class LoginResult:
    """Return value for a successful login."""

    access_token: str
    token_type: str


class IdentityService:
    """Coordinates login validation and token generation."""

    def __init__(self, repository: IdentityRepository) -> None:
        self._repository = repository

    def login(self, *, tenant_id: UUID, email: str, password: str) -> LoginResult:
        user = self._authenticate_user(tenant_id=tenant_id, email=email, password=password)
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )
        return LoginResult(access_token=access_token, token_type="bearer")

    def _authenticate_user(self, *, tenant_id: UUID, email: str, password: str) -> UserModel:
        user = self._repository.get_active_user_by_tenant_and_email(
            tenant_id=tenant_id,
            email=email,
        )
        if user is not None and verify_password(password, user.password_hash):
            return user

        raise AppException("Invalid credentials", status_code=401)
