import json

from app.lambdas import proposal_sqs_handler


def test_lambda_handler_processes_all_sqs_records(monkeypatch):
    processed_messages: list[str] = []
    monkeypatch.setattr(
        proposal_sqs_handler,
        "process_queue_message",
        lambda body: processed_messages.append(body),
    )

    result = proposal_sqs_handler.handler(
        {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(
                        {"action": "simulate", "proposal_id": "one", "job_id": "job-one"}
                    ),
                },
                {
                    "messageId": "msg-2",
                    "body": json.dumps(
                        {"action": "submit", "proposal_id": "two", "job_id": "job-two"}
                    ),
                },
            ]
        },
        None,
    )

    assert result == {"processed_records": 2}
    assert processed_messages == [
        '{"action": "simulate", "proposal_id": "one", "job_id": "job-one"}',
        '{"action": "submit", "proposal_id": "two", "job_id": "job-two"}',
    ]


def test_lambda_handler_returns_partial_failures(monkeypatch):
    def raise_error(_body: str) -> None:
        raise RuntimeError("processing failed")

    monkeypatch.setattr(proposal_sqs_handler, "process_queue_message", raise_error)

    result = proposal_sqs_handler.handler(
        {
            "Records": [
                {
                    "messageId": "msg-1",
                    "body": json.dumps(
                        {"action": "simulate", "proposal_id": "one", "job_id": "job-one"}
                    ),
                }
            ]
        },
        None,
    )

    assert result == {
        "processed_records": 0,
        "batchItemFailures": [{"itemIdentifier": "msg-1"}],
    }
