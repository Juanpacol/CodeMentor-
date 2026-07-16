from httpx import AsyncClient

from logica.modules.users.models import Institution
from tests.integration.conftest import auth_headers, register_and_login


async def test_validate_valid_program(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.post(
        "/sandbox/pseint/validate",
        json={"source": 'Proceso P\nEscribir "hola";\nFinProceso'},
        headers=auth_headers(access),
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


async def test_validate_invalid_program_reports_line(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.post(
        "/sandbox/pseint/validate",
        json={"source": "Proceso P\nSi x Entonces\nFinProceso"},
        headers=auth_headers(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["error_line"] is not None


async def test_run_program_returns_stdout_and_trace(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.post(
        "/sandbox/pseint/run",
        json={
            "source": (
                'Proceso P\nDefinir x Como Entero;\nx <- 2;\nEscribir "x vale ", x;\nFinProceso'
            )
        },
        headers=auth_headers(access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stdout"] == ["x vale 2"]
    assert body["variables"]["x"] == 2
    assert len(body["trace"]) == 3  # Definir, asignación, Escribir


async def test_run_infinite_loop_rejected(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.post(
        "/sandbox/pseint/run",
        json={
            "source": 'Proceso P\nMientras Verdadero Hacer\nEscribir "x";\nFinMientras\nFinProceso'
        },
        headers=auth_headers(access),
    )
    assert resp.status_code == 422


async def test_sandbox_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/sandbox/pseint/validate", json={"source": "Proceso P\nFinProceso"})
    assert resp.status_code == 401
