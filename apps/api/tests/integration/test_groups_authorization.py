from httpx import AsyncClient

from logica.modules.users.models import Institution
from tests.integration.conftest import auth_headers, register_and_login


async def test_student_cannot_create_group(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.post(
        "/groups", json={"name": "Intento de grupo"}, headers=auth_headers(access)
    )
    assert resp.status_code == 403


async def test_teacher_can_create_and_list_own_group(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    created = await client.post("/groups", json={"name": "10-1"}, headers=auth_headers(access))
    assert created.status_code == 201
    assert created.json()["invite_code"]

    listed = await client.get("/groups/mine", headers=auth_headers(access))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_teacher_cannot_edit_another_teachers_group(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    access_a, _ = await register_and_login(client, email=f"doc-a@{domain}", role="teacher")
    access_b, _ = await register_and_login(client, email=f"doc-b@{domain}", role="teacher")

    created = await client.post(
        "/groups", json={"name": "Grupo de A"}, headers=auth_headers(access_a)
    )
    group_id = created.json()["id"]

    resp = await client.patch(
        f"/groups/{group_id}", json={"name": "Hackeado"}, headers=auth_headers(access_b)
    )
    assert resp.status_code == 403


async def test_student_join_by_code_and_appears_in_mine(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    created = await client.post(
        "/groups", json={"name": "10-2"}, headers=auth_headers(teacher_access)
    )
    invite_code = created.json()["invite_code"]

    before = await client.get("/groups/mine", headers=auth_headers(student_access))
    assert before.json() == []

    joined = await client.post(
        "/groups/join", json={"invite_code": invite_code}, headers=auth_headers(student_access)
    )
    assert joined.status_code == 201

    after = await client.get("/groups/mine", headers=auth_headers(student_access))
    assert len(after.json()) == 1
    assert after.json()[0]["name"] == "10-2"

    duplicate_join = await client.post(
        "/groups/join", json={"invite_code": invite_code}, headers=auth_headers(student_access)
    )
    assert duplicate_join.status_code == 409


async def test_archived_group_disappears_from_teacher_listing(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    created = await client.post(
        "/groups", json={"name": "Se va a archivar"}, headers=auth_headers(access)
    )
    group_id = created.json()["id"]

    archived = await client.post(f"/groups/{group_id}/archive", headers=auth_headers(access))
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None

    listed = await client.get("/groups/mine", headers=auth_headers(access))
    assert listed.json() == []


async def test_student_cannot_enroll_csv(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    created = await client.post(
        "/groups", json={"name": "10-3"}, headers=auth_headers(teacher_access)
    )
    group_id = created.json()["id"]

    csv_bytes = b"email,full_name\nnuevo@example.com,Nuevo Estudiante\n"
    resp = await client.post(
        f"/groups/{group_id}/enroll-csv",
        files={"file": ("enroll.csv", csv_bytes, "text/csv")},
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403
