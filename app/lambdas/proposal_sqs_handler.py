"""Lambda handler for SQS-triggered proposal jobs."""

from __future__ import annotations

from app.workers.proposal_processor import process_queue_message


def handler(event: dict, _context: object) -> dict:
    records = event.get("Records", [])
    for record in records:
        process_queue_message(record["body"])

    return {"processed_records": len(records)}
