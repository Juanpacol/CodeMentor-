"""El limiter global de la app (`core/rate_limit.py`) se queda `enabled=False`
fuera de ENV=prod para no romper el resto de la suite (decenas de tests
golpean /auth/login repetidamente). Por eso la lógica de enforcement en sí
se prueba aquí contra una app FastAPI aislada con el limiter forzado a
`enabled=True`, en vez de reusar el fixture `client` compartido."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def _build_app() -> FastAPI:
    limiter = Limiter(key_func=get_remote_address, enabled=True)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": "Demasiados intentos."})

    @app.get("/ping")
    @limiter.limit("2/minute")
    async def ping(request: Request) -> dict[str, str]:
        return {"ok": "pong"}

    return app


async def test_limiter_allows_up_to_the_limit_then_blocks() -> None:
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/ping")).status_code == 200
        assert (await client.get("/ping")).status_code == 200

        blocked = await client.get("/ping")
        assert blocked.status_code == 429
        assert blocked.json() == {"detail": "Demasiados intentos."}
