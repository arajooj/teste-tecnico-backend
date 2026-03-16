from uuid import uuid4

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password_roundtrip():
    password_hash = hash_password("super-secret")

    assert password_hash != "super-secret"
    assert verify_password("super-secret", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_decode_access_token_rejects_malformed_token():
    with pytest.raises(AppException, match="Invalid or expired token"):
        decode_access_token("not-a-jwt")


def test_decode_access_token_rejects_invalid_uuid_payload():
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "not-a-uuid",
            "tenant_id": str(uuid4()),
            "role": "admin",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AppException, match="Invalid or expired token"):
        decode_access_token(token)


def test_get_current_user_rejects_missing_credentials():
    with pytest.raises(AppException, match="Authentication required"):
        get_current_user(None)


def test_get_current_user_decodes_credentials():
    token = create_access_token(user_id=uuid4(), tenant_id=uuid4(), role="operator")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    authenticated_user = get_current_user(credentials)

    assert authenticated_user.role == "operator"
