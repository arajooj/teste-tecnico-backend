"""Webhook API routes."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.proposals.infrastructure.repository import ProposalRepository
from app.modules.webhooks.api.schemas import BankCallbackPayload
from app.modules.webhooks.application.services import BankCallbackCommand, WebhookService
from app.modules.webhooks.infrastructure.repository import WebhookRepository

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/bank-callback", status_code=status.HTTP_204_NO_CONTENT)
def receive_bank_callback(
    payload: BankCallbackPayload,
    callback_token: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> Response:
    repository = WebhookRepository(ProposalRepository(db))
    service = WebhookService(repository)
    service.handle_bank_callback(
        command=BankCallbackCommand(
            callback_token=callback_token,
            protocol=payload.protocol,
            event=payload.event,
            status=payload.status,
            data=payload.data,
            timestamp=payload.timestamp,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
