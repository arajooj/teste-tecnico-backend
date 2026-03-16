"""Lambda handler for SQS-triggered proposal jobs."""

from __future__ import annotations

import logging

from app.workers.proposal_processor import process_queue_message

logger = logging.getLogger(__name__)


def handler(event: dict, _context: object) -> dict:
    records = event.get("Records", [])
    logger.info("Received SQS batch", extra={"records_count": len(records)})
    batch_failures: list[dict[str, str]] = []
    for record in records:
        try:
            process_queue_message(record["body"])
        except Exception:
            message_id = record.get("messageId")
            if message_id is not None:
                batch_failures.append({"itemIdentifier": message_id})
            else:  # pragma: no cover
                raise

    processed_records = len(records) - len(batch_failures)
    logger.info(
        "Finished SQS batch",
        extra={
            "processed_records": processed_records,
            "failed_records": len(batch_failures),
        },
    )
    if batch_failures:
        return {
            "processed_records": processed_records,
            "batchItemFailures": batch_failures,
        }
    return {"processed_records": processed_records}
