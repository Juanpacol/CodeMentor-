import uuid

import pytest
from httpx import AsyncClient

from logica.db import get_session_factory
from logica.modules.reports.repository import get_report_job
from logica.modules.reports.service import generate_group_report
from logica.modules.users.models import Institution
from tests.integration.conftest import (
    auth_headers,
    create_group,
    join_group,
    register_and_login,
)


async def test_request_report_requires_teacher(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")
    group = await create_group(client, teacher_access)

    resp = await client.post(
        f"/groups/{group['id']}/reports",
        json={"format": "xlsx"},
        headers=auth_headers(student_access),
    )
    assert resp.status_code == 403


async def test_request_report_returns_pending_job(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    resp = await client.post(
        f"/groups/{group['id']}/reports",
        json={"format": "xlsx"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "pending"
    assert job["format"] == "xlsx"

    fetched = await client.get(f"/reports/{job['id']}", headers=auth_headers(teacher_access))
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "pending"


async def test_download_not_ready_returns_conflict(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    created = await client.post(
        f"/groups/{group['id']}/reports",
        json={"format": "xlsx"},
        headers=auth_headers(teacher_access),
    )
    job_id = created.json()["id"]

    resp = await client.get(f"/reports/{job_id}/download", headers=auth_headers(teacher_access))
    assert resp.status_code == 409


async def test_full_xlsx_report_lifecycle(client: AsyncClient, institution: Institution) -> None:
    """Simulates what the arq worker does after `generate_group_report_job`
    is enqueued — running it inline here keeps the test fast/deterministic
    instead of depending on a real worker process consuming the queue."""
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")
    group = await create_group(client, teacher_access)
    await join_group(client, student_access, group["invite_code"])

    created = await client.post(
        f"/groups/{group['id']}/reports",
        json={"format": "xlsx"},
        headers=auth_headers(teacher_access),
    )
    job_id = created.json()["id"]

    session_factory = get_session_factory()
    async with session_factory() as db:
        await generate_group_report(db, uuid.UUID(job_id))
        await db.commit()

    status_resp = await client.get(f"/reports/{job_id}", headers=auth_headers(teacher_access))
    assert status_resp.json()["status"] == "done"

    download = await client.get(f"/reports/{job_id}/download", headers=auth_headers(teacher_access))
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(download.content) > 0

    async with session_factory() as db:
        job = await get_report_job(db, uuid.UUID(job_id))
        assert job is not None
        assert job.file_path is not None


async def test_report_requires_valid_period(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    resp = await client.post(
        f"/groups/{group['id']}/reports",
        json={"format": "xlsx", "period_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 404


@pytest.mark.pdf
async def test_full_pdf_report_lifecycle(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    group = await create_group(client, teacher_access)

    created = await client.post(
        f"/groups/{group['id']}/reports",
        json={"format": "pdf"},
        headers=auth_headers(teacher_access),
    )
    job_id = created.json()["id"]

    session_factory = get_session_factory()
    async with session_factory() as db:
        await generate_group_report(db, uuid.UUID(job_id))
        await db.commit()

    download = await client.get(f"/reports/{job_id}/download", headers=auth_headers(teacher_access))
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")
