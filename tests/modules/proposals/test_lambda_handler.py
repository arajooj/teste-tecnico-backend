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
                {"body": json.dumps({"action": "simulate", "proposal_id": "one"})},
                {"body": json.dumps({"action": "submit", "proposal_id": "two"})},
            ]
        },
        None,
    )

    assert result == {"processed_records": 2}
    assert processed_messages == [
        '{"action": "simulate", "proposal_id": "one"}',
        '{"action": "submit", "proposal_id": "two"}',
    ]


def test_lambda_handler_propagates_processing_errors(monkeypatch):
    def raise_error(_body: str) -> None:
        raise RuntimeError("processing failed")

    monkeypatch.setattr(proposal_sqs_handler, "process_queue_message", raise_error)

    try:
        proposal_sqs_handler.handler(
            {"Records": [{"body": json.dumps({"action": "simulate", "proposal_id": "one"})}]},
            None,
        )
    except RuntimeError as exc:
        assert str(exc) == "processing failed"
    else:  # pragma: no cover
        raise AssertionError("Lambda handler should propagate processing errors")
