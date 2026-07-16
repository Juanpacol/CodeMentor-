from httpx import AsyncClient

from logica.db import get_session_factory
from logica.modules.users import service
from logica.modules.users.models import Institution
from tests.integration.conftest import auth_headers, register_and_login


async def test_register_login_refresh_me_flow(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    email = f"docente@{domain}"

    access, refresh = await register_and_login(
        client, email=email, role="teacher", full_name="Docente Uno"
    )

    me = await client.get("/users/me", headers=auth_headers(access))
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["role"] == "teacher"

    refreshed = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]

    me_again = await client.get("/users/me", headers=auth_headers(new_access))
    assert me_again.status_code == 200


async def test_register_duplicate_email_rejected(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    email = f"repetido@{domain}"
    payload = {
        "email": email,
        "password": "Sup3rSecreta!",
        "full_name": "Alguien",
        "role": "student",
    }
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 422


async def test_register_without_domain_or_student_code_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/register",
        json={
            "email": "nadie@dominio-externo.com",
            "password": "Sup3rSecreta!",
            "full_name": "Nadie",
            "role": "student",
        },
    )
    assert resp.status_code == 422


async def test_register_student_with_code_fallback_when_single_institution(
    client: AsyncClient, institution: Institution
) -> None:
    resp = await client.post(
        "/auth/register",
        json={
            "email": "estudiante@dominio-externo.com",
            "password": "Sup3rSecreta!",
            "full_name": "Estudiante Externo",
            "role": "student",
            "student_code": "E999",
        },
    )
    assert resp.status_code == 201


async def test_login_wrong_password_rejected(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    email = f"clave@{domain}"
    await register_and_login(client, email=email, password="ClaveCorrecta1!")

    resp = await client.post("/auth/login", json={"email": email, "password": "ClaveIncorrecta1!"})
    assert resp.status_code == 422


async def test_password_reset_flow(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    email = f"reset@{domain}"
    await register_and_login(client, email=email, password="ClaveOriginal1!")

    resp = await client.post("/auth/password-reset/request", json={"email": email})
    assert resp.status_code == 202

    # Dev mode has no email provider; unknown emails must not leak existence (202 too).
    resp_unknown = await client.post(
        "/auth/password-reset/request", json={"email": f"no-existe@{domain}"}
    )
    assert resp_unknown.status_code == 202


async def test_password_reset_confirm_changes_password(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    email = f"reset-confirm@{domain}"
    await register_and_login(client, email=email, password="ClaveOriginal1!")

    session_factory = get_session_factory()
    async with session_factory() as db:
        raw_token = await service.request_password_reset(db, email)
        await db.commit()
    assert raw_token is not None

    confirm = await client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "ClaveNueva123!"},
    )
    assert confirm.status_code == 204

    old_login = await client.post(
        "/auth/login", json={"email": email, "password": "ClaveOriginal1!"}
    )
    assert old_login.status_code == 422

    new_login = await client.post(
        "/auth/login", json={"email": email, "password": "ClaveNueva123!"}
    )
    assert new_login.status_code == 200
