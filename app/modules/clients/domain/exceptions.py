"""Domain-level exceptions for the clients module."""

from app.core.exceptions import AppException


class ClientNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__("Client not found", status_code=404)


class ClientAlreadyExistsError(AppException):
    def __init__(self) -> None:
        super().__init__("Client with this CPF already exists", status_code=409)
