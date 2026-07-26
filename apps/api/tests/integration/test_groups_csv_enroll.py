from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.users.models import Institution
from tests.integration.conftest import auth_headers, register_and_login


async def test_bulk_enroll_csv_with_valid_and_corrupt_rows(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    created = await client.post(
        "/groups", json={"name": "10-4"}, headers=auth_headers(teacher_access)
    )
    group_id = created.json()["id"]

    csv_content = (
        b"email,full_name,student_code\n"
        b"valido1@example.com,Valido Uno,S100\n"
        b",Sin Correo,S101\n"
        b"valido2@example.com,,S102\n"
        b"valido1@example.com,Valido Uno Duplicado,S103\n"
    )

    resp = await client.post(
        f"/groups/{group_id}/enroll-csv",
        files={"file": ("enroll.csv", csv_content, "text/csv")},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 200
    result = resp.json()

    assert result["enrolled"] == 1
    assert len(result["created_accounts"]) == 1
    assert result["created_accounts"][0]["email"] == "valido1@example.com"
    assert len(result["errors"]) == 3

    reasons = {e["reason"] for e in result["errors"]}
    assert any("correo" in r for r in reasons)
    assert any("nombre" in r for r in reasons)
    assert any("duplicado" in r for r in reasons)


async def test_enrolled_student_can_login_with_temporary_password(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    created = await client.post(
        "/groups", json={"name": "10-5"}, headers=auth_headers(teacher_access)
    )
    group_id = created.json()["id"]

    csv_content = b"email,full_name\nrecien.creado@example.com,Recien Creado\n"
    resp = await client.post(
        f"/groups/{group_id}/enroll-csv",
        files={"file": ("enroll.csv", csv_content, "text/csv")},
        headers=auth_headers(teacher_access),
    )
    temp_password = resp.json()["created_accounts"][0]["temporary_password"]

    login = await client.post(
        "/auth/login",
        json={"email": "recien.creado@example.com", "password": temp_password},
    )
    assert login.status_code == 200

    student_access = login.json()["access_token"]
    mine = await client.get("/groups/mine", headers=auth_headers(student_access))
    assert len(mine.json()) == 1
    assert mine.json()[0]["name"] == "10-5"


async def test_bulk_enroll_csv_isolates_row_failure_from_others(
    client: AsyncClient, institution: Institution, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DB-level failure on one row's write (e.g. a unique-email race with a
    concurrent enrollment) must not abort every other row in the same file —
    each row runs in its own SAVEPOINT, same idiom as
    content.service.enable_scheduled_topics."""
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    created = await client.post(
        "/groups", json={"name": "10-7"}, headers=auth_headers(teacher_access)
    )
    group_id = created.json()["id"]

    csv_content = (
        b"email,full_name\n"
        b"buena1@example.com,Buena Uno\n"
        b"rompe@example.com,Rompe Fila\n"
        b"buena2@example.com,Buena Dos\n"
    )

    original_flush = AsyncSession.flush
    call_count = 0

    async def flaky_flush(self: AsyncSession, *args: Any, **kwargs: Any) -> None:
        nonlocal call_count
        call_count += 1
        # Calls 1-2 are "buena1"'s user-creation + end-of-row flush; call 3
        # is "rompe"'s user-creation flush — force only that one to fail.
        if call_count == 3:
            raise RuntimeError("simulated DB failure for this row")
        await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", flaky_flush)

    resp = await client.post(
        f"/groups/{group_id}/enroll-csv",
        files={"file": ("enroll.csv", csv_content, "text/csv")},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()

    assert result["enrolled"] == 2
    emails = {a["email"] for a in result["created_accounts"]}
    assert emails == {"buena1@example.com", "buena2@example.com"}
    assert len(result["errors"]) == 1
    assert result["errors"][0]["raw_row"] == "rompe@example.com"


async def test_bulk_enroll_csv_missing_required_columns_returns_conflict(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    created = await client.post(
        "/groups", json={"name": "10-6"}, headers=auth_headers(teacher_access)
    )
    group_id = created.json()["id"]

    csv_content = b"correo,nombre\nx@example.com,Alguien\n"
    resp = await client.post(
        f"/groups/{group_id}/enroll-csv",
        files={"file": ("enroll.csv", csv_content, "text/csv")},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 409
