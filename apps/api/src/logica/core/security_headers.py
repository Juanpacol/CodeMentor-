from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from logica.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Cabeceras de seguridad básicas (RE-08 hardening) en toda respuesta.

    HSTS solo se envía con ENV=prod: en dev/local la API corre sobre HTTP
    plano y un HSTS prematuro podría dejar el navegador del desarrollador
    forzando HTTPS en localhost.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if get_settings().env == "prod":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
