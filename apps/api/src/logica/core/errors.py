class LogicaError(Exception):
    """Base exception for all domain errors in the platform."""

    status_code: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(LogicaError):
    status_code = 404


class PermissionDeniedError(LogicaError):
    status_code = 403


class ConflictError(LogicaError):
    status_code = 409


class ValidationDomainError(LogicaError):
    status_code = 422
