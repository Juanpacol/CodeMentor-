from httpx import AsyncClient

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
