"""Application services for identity authentication flows."""

from __future__ import annotations

from dataclasses import dataclass

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

    def login(self, *, email: str, password: str) -> LoginResult:
        user = self._authenticate_user(email=email, password=password)
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )
        return LoginResult(access_token=access_token, token_type="bearer")

    def _authenticate_user(self, *, email: str, password: str) -> UserModel:
        for user in self._repository.list_active_users_by_email(email=email):
            if verify_password(password, user.password_hash):
                return user

        raise AppException("Invalid credentials", status_code=401)
