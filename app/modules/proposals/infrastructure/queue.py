"""SQS queue adapter used by asynchronous proposal workflows."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import boto3

from app.core.config import get_settings


@dataclass(frozen=True)
class ProposalQueueMessage:
    action: str
    proposal_id: str
    job_id: str


class ProposalQueue:
    """Publishes proposal jobs to SQS."""

    def __init__(self, sqs_client=None, queue_name: str | None = None) -> None:
        settings = get_settings()
        self._queue_name = queue_name or settings.sqs_queue_name
        self._queue_url: str | None = None
        self._client = sqs_client or boto3.client(
            "sqs",
            endpoint_url=settings.aws_endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def send_message(self, *, action: str, proposal_id: str, job_id: str) -> None:
        payload = ProposalQueueMessage(action=action, proposal_id=proposal_id, job_id=job_id)
        self._client.send_message(
            QueueUrl=self._get_queue_url(),
            MessageBody=json.dumps(asdict(payload)),
        )

    def _get_queue_url(self) -> str:
        if self._queue_url is None:
            response = self._client.get_queue_url(QueueName=self._queue_name)
            self._queue_url = response["QueueUrl"]
        return self._queue_url
