"""Lambda handler for SQS-triggered proposal jobs."""

from __future__ import annotations

import logging

from app.workers.proposal_processor import process_queue_message

logger = logging.getLogger(__name__)


def handler(event: dict, _context: object) -> dict:
    records = event.get("Records", [])
    logger.info("Received SQS batch", extra={"records_count": len(records)})
    for record in records:
        process_queue_message(record["body"])

    logger.info("Finished SQS batch", extra={"processed_records": len(records)})
    return {"processed_records": len(records)}
