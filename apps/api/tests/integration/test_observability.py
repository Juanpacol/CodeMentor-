import uuid
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from logica.core.audit import AuditLog, record_audit
from logica.db import get_session_factory
from logica.main import create_app
from logica.modules.observability import repository as observability_repository
from logica.modules.observability.models import ErrorLog
from logica.modules.users.models import Institution
from logica.workers.settings import (
    AUDIT_LOG_RETENTION_DAYS,
    ERROR_LOG_RETENTION_DAYS,
    prune_observability_logs_job,
    record_error_log_job,
)
from tests.integration.conftest import auth_headers, register_and_login


async def test_unhandled_exception_returns_generic_500_without_leaking(
    institution: Institution,
) -> None:
    """A route that raises an uncaught exception must never leak the raw
    message to the client — this is what makes an unexpected 500 different
    from an expected LogicaError."""
    app = create_app()

    @app.get("/__test_boom__")
    async def _boom() -> None:
        raise RuntimeError("boom secreto: no debería verse en la respuesta")

    # `raise_app_exceptions=False`: Starlette's ServerErrorMiddleware sends
    # the handled 500 response and then re-raises the original exception on
    # purpose (so a real ASGI server like uvicorn can still log it) — en
    # producción el cliente ya recibió la respuesta antes de ese re-raise,
    # pero httpx por defecto lo vuelve a lanzar en el test. Sin esta bandera
    # el test fallaría con el RuntimeError crudo en vez de poder inspeccionar
    # la respuesta ya enviada.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        resp = await client.get("/__test_boom__")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Error interno del servidor."}
    assert "boom secreto" not in resp.text


async def test_logica_error_still_returns_its_own_status_and_message(
    client: AsyncClient, institution: Institution
) -> None:
    """A regular domain error (LogicaError subclass) must keep going through
    its own specific handler — the broad Exception handler must never shadow
    it, and no error_logs row should be created for an expected error."""
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    resp = await client.get(f"/reports/{uuid.uuid4()}", headers=auth_headers(teacher_access))
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Reporte no encontrado"}

    session_factory = get_session_factory()
    async with session_factory() as db:
        rows = (await db.execute(select(ErrorLog))).scalars().all()
    assert len(rows) == 0


async def test_record_error_log_job_persists_a_row(institution: Institution) -> None:
    payload = {
        "institution_id": str(institution.id),
        "user_id": None,
        "path": "/algo",
        "method": "GET",
        "status_code": 500,
        "exception_type": "RuntimeError",
        "message": "algo se rompió",
        "stacktrace": "Traceback (most recent call last): ...",
    }
    await record_error_log_job({}, payload)

    session_factory = get_session_factory()
    async with session_factory() as db:
        rows = (
            (await db.execute(select(ErrorLog).where(ErrorLog.institution_id == institution.id)))
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].exception_type == "RuntimeError"
    assert rows[0].message == "algo se rompió"


async def test_list_errors_scoped_to_institution_and_redacts_stacktrace_for_teacher(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    session_factory = get_session_factory()
    async with session_factory() as db:
        await observability_repository.create_error_log(
            db,
            institution_id=institution.id,
            user_id=None,
            path="/roto",
            method="POST",
            status_code=500,
            exception_type="ValueError",
            message="mensaje de prueba",
            stacktrace="stack completo aquí",
        )
        await db.commit()

    resp = await client.get("/observability/errors", headers=auth_headers(teacher_access))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "mensaje de prueba"
    assert body["items"][0]["stacktrace"] is None  # oculto para docente

    forbidden = await client.get("/observability/errors", headers=auth_headers(student_access))
    assert forbidden.status_code == 403


async def test_list_errors_filters_by_status_code(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")

    session_factory = get_session_factory()
    async with session_factory() as db:
        await observability_repository.create_error_log(
            db,
            institution_id=institution.id,
            user_id=None,
            path="/a",
            method="GET",
            status_code=500,
            exception_type="ValueError",
            message="m1",
            stacktrace=None,
        )
        await observability_repository.create_error_log(
            db,
            institution_id=institution.id,
            user_id=None,
            path="/b",
            method="GET",
            status_code=502,
            exception_type="TimeoutError",
            message="m2",
            stacktrace=None,
        )
        await db.commit()

    resp = await client.get(
        "/observability/errors",
        params={"status_code": 502},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["exception_type"] == "TimeoutError"


async def test_audit_log_listing_and_filters(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    session_factory = get_session_factory()
    async with session_factory() as db:
        await record_audit(
            db,
            institution_id=institution.id,
            actor_user_id=None,
            action="role_changed",
            target_type="User",
            target_id="abc",
            details={"from": "student", "to": "teacher"},
        )
        await db.commit()

    resp = await client.get("/observability/audit", headers=auth_headers(teacher_access))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "role_changed"

    filtered = await client.get(
        "/observability/audit",
        params={"action": "no_existe"},
        headers=auth_headers(teacher_access),
    )
    assert filtered.json()["total"] == 0

    forbidden = await client.get("/observability/audit", headers=auth_headers(student_access))
    assert forbidden.status_code == 403


async def test_prune_observability_logs_deletes_only_old_rows(institution: Institution) -> None:
    session_factory = get_session_factory()
    now = datetime.now(UTC)
    old_error_at = now - timedelta(days=ERROR_LOG_RETENTION_DAYS + 1)
    old_audit_at = now - timedelta(days=AUDIT_LOG_RETENTION_DAYS + 1)

    async with session_factory() as db:
        await observability_repository.create_error_log(
            db,
            institution_id=institution.id,
            user_id=None,
            path="/viejo",
            method="GET",
            status_code=500,
            exception_type="ValueError",
            message="viejo",
            stacktrace=None,
        )
        await observability_repository.create_error_log(
            db,
            institution_id=institution.id,
            user_id=None,
            path="/reciente",
            method="GET",
            status_code=500,
            exception_type="ValueError",
            message="reciente",
            stacktrace=None,
        )
        await record_audit(
            db,
            institution_id=institution.id,
            actor_user_id=None,
            action="viejo",
            target_type="User",
            target_id="x",
        )
        await db.commit()

        # TimestampMixin usa server_default en el INSERT — para simular una
        # fila vieja hay que pisar `created_at` con un UPDATE explícito.
        old_error = (
            await db.execute(select(ErrorLog).where(ErrorLog.path == "/viejo"))
        ).scalar_one()
        old_error.created_at = old_error_at
        old_audit = (
            await db.execute(select(AuditLog).where(AuditLog.action == "viejo"))
        ).scalar_one()
        old_audit.created_at = old_audit_at
        await db.commit()

    await prune_observability_logs_job({})

    async with session_factory() as db:
        remaining_errors = {e.path for e in (await db.execute(select(ErrorLog))).scalars().all()}
        remaining_audit = {a.action for a in (await db.execute(select(AuditLog))).scalars().all()}

    assert remaining_errors == {"/reciente"}
    assert "viejo" not in remaining_audit
