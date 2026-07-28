from typing import Any


class LogicaError(Exception):
    """Base exception for all domain errors in the platform."""

    status_code: int = 400
    #: Identificador estable para que la UI decida qué ofrecer (reintentar,
    #: esperar la cuota, revisar la plantilla) sin parsear el texto en español.
    code: str = "error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        # `message` es el texto amable que ve cualquiera; `details` es lo
        # accionable para quien tiene que arreglarlo — qué proveedor de IA
        # falló y con qué error, qué campo no validó. Antes esto solo existía
        # en los logs del servidor, así que el docente veía "no está
        # disponible" sin ninguna forma de avanzar.
        self.details = details


class NotFoundError(LogicaError):
    status_code = 404
    code = "not_found"


class PermissionDeniedError(LogicaError):
    status_code = 403
    code = "permission_denied"


class ConflictError(LogicaError):
    status_code = 409
    code = "conflict"


class ValidationDomainError(LogicaError):
    status_code = 422
    code = "validation"


class ServiceUnavailableError(LogicaError):
    """§9.4 "plan de contingencia sin IA": a downstream dependency (every LLM
    provider in the harness's fallback chain, the sandbox, etc.) is down.
    Distinct from a 500 — this is an expected, handled failure mode with a
    clear message, not a bug."""

    status_code = 503
    code = "service_unavailable"
