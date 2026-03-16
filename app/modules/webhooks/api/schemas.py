"""API schemas for webhook callbacks."""

from pydantic import BaseModel, Field


class BankCallbackPayload(BaseModel):
    protocol: str
    event: str
    status: str
    data: dict = Field(default_factory=dict)
    timestamp: str | None = None
