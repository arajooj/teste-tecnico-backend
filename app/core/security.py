"""Security helpers for password hashing and JWT authentication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import AppException

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Authenticated request context extracted from a JWT."""

    user_id: UUID
    tenant_id: UUID
    role: str


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain-text password against its hash."""
    return pwd_context.verify(password, password_hash)


def create_access_token(*, user_id: UUID, tenant_id: UUID, role: str) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AuthenticatedUser:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    invalid_token = AppException("Invalid or expired token", status_code=401)

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload["sub"]
        tenant_id = payload["tenant_id"]
        role = payload["role"]
    except (JWTError, KeyError, ValueError) as exc:
        raise invalid_token from exc

    try:
        return AuthenticatedUser(
            user_id=UUID(user_id),
            tenant_id=UUID(tenant_id),
            role=str(role),
        )
    except ValueError as exc:
        raise invalid_token from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Resolve the authenticated user context from the Authorization header."""
    if credentials is None:
        raise AppException("Authentication required", status_code=401)

    return decode_access_token(credentials.credentials)
