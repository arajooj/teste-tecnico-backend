"""Domain exceptions for the proposals module."""

from app.core.exceptions import AppException


class ProposalNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__("Proposal not found", status_code=404)


class ProposalClientNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__("Client not found", status_code=404)


class InvalidProposalStateError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class ProposalDispatchError(AppException):
    def __init__(self) -> None:
        super().__init__(
            "Proposal persisted but the async job could not be published",
            status_code=503,
        )
