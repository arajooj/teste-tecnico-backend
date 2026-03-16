"""Authentication API routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identity.api.schemas import LoginRequest, LoginResponse
from app.modules.identity.application.services import IdentityService
from app.modules.identity.infrastructure.repository import IdentityRepository

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    repository = IdentityRepository(db)
    service = IdentityService(repository)
    result = service.login(
        tenant_id=payload.tenant_id,
        email=payload.email,
        password=payload.password,
    )
    return LoginResponse(
        access_token=result.access_token,
        token_type=result.token_type,
    )
