"""Smoke tests against real infra (Postgres/Redis). Require `make up` or CI services."""

from httpx import AsyncClient


async def test_health_db(client: AsyncClient) -> None:
    response = await client.get("/health/db")
    assert response.status_code == 200


async def test_health_redis(client: AsyncClient) -> None:
    response = await client.get("/health/redis")
    assert response.status_code == 200
