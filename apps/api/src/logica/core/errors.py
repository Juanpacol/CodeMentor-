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


class ServiceUnavailableError(LogicaError):
    """§9.4 "plan de contingencia sin IA": a downstream dependency (every LLM
    provider in the harness's fallback chain, the sandbox, etc.) is down.
    Distinct from a 500 — this is an expected, handled failure mode with a
    clear message, not a bug."""

    status_code = 503
