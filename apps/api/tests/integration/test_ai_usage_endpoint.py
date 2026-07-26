import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient

from logica.ai import repository as ai_repository
from logica.db import get_session_factory
from logica.modules.users.models import Institution
from tests.integration.conftest import auth_headers, get_user_by_email, register_and_login


async def _seed_interaction(
    institution_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    task: str,
    model: str,
    cost_usd: str,
    created_at: datetime | None = None,
) -> None:
    session_factory = get_session_factory()
    async with session_factory() as db:
        entry = await ai_repository.record_interaction(
            db,
            institution_id=institution_id,
            user_id=user_id,
            task=task,
            model=model,
            response_text="respuesta de prueba",
            prompt_tokens=100,
            completion_tokens=50,
            from_cache=False,
            cost_usd=Decimal(cost_usd),
        )
        if created_at is not None:
            entry.created_at = created_at
        await db.commit()


async def test_ai_usage_scoped_to_institution(
    client: AsyncClient, institution: Institution
) -> None:
    """El hallazgo de mayor valor acá, dado que la tenencia es 100%
    app-level (ADR-006): el endpoint de una institución nunca debe devolver
    filas de otra."""
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    teacher = await get_user_by_email(f"doc@{domain}")

    session_factory = get_session_factory()
    async with session_factory() as db:
        other = Institution(name="Otro colegio", email_domains=["otro-colegio.edu.co"])
        db.add(other)
        await db.commit()
        await db.refresh(other)

    await _seed_interaction(
        institution.id,
        teacher.id,
        task="progressive_hint",
        model="groq/llama-3.1-8b-instant",
        cost_usd="0.05",
    )
    await _seed_interaction(
        other.id,
        teacher.id,
        task="progressive_hint",
        model="groq/llama-3.1-8b-instant",
        cost_usd="99.00",
    )

    resp = await client.get("/observability/ai/usage", headers=auth_headers(teacher_access))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["cost_usd"] == 0.05
    assert body["budget"]["month_to_date_usd"] == 0.05


async def test_ai_usage_forbidden_for_student(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    student_access, _ = await register_and_login(client, email=f"est@{domain}", role="student")

    resp = await client.get("/observability/ai/usage", headers=auth_headers(student_access))
    assert resp.status_code == 403


async def test_ai_usage_row_on_date_to_after_midnight_is_included(
    client: AsyncClient, institution: Institution
) -> None:
    """Regresión de la cota semiabierta: una fila creada el día `date_to` a
    las 23:00 debe seguir apareciendo — `list_error_logs` en
    `observability/repository.py` sí tiene este bug (compara `created_at`
    contra un `date` pelado); acá se usa `< date_to + 1 día` a propósito."""
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    teacher = await get_user_by_email(f"doc@{domain}")

    today = date.today()
    late_today = datetime.combine(today, datetime.min.time(), tzinfo=UTC) + timedelta(hours=23)
    await _seed_interaction(
        institution.id,
        teacher.id,
        task="progressive_hint",
        model="groq/llama-3.1-8b-instant",
        cost_usd="0.10",
        created_at=late_today,
    )

    resp = await client.get(
        "/observability/ai/usage",
        params={"date_from": str(today), "date_to": str(today)},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["cost_usd"] == 0.10


async def test_ai_usage_group_by_model(client: AsyncClient, institution: Institution) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    teacher = await get_user_by_email(f"doc@{domain}")

    await _seed_interaction(
        institution.id,
        teacher.id,
        task="progressive_hint",
        model="groq/llama-3.1-8b-instant",
        cost_usd="0.01",
    )
    await _seed_interaction(
        institution.id,
        teacher.id,
        task="exercise_generation",
        model="gemini/gemini-1.5-pro",
        cost_usd="0.20",
    )

    resp = await client.get(
        "/observability/ai/usage",
        params={"group_by": "model"},
        headers=auth_headers(teacher_access),
    )
    assert resp.status_code == 200, resp.text
    keys = {item["key"] for item in resp.json()["items"]}
    assert keys == {"groq/llama-3.1-8b-instant", "gemini/gemini-1.5-pro"}


async def test_budget_level_critical_above_ninety_percent(
    client: AsyncClient, institution: Institution
) -> None:
    domain = institution.email_domains[0]
    teacher_access, _ = await register_and_login(client, email=f"doc@{domain}", role="teacher")
    teacher = await get_user_by_email(f"doc@{domain}")

    # settings.ai_monthly_cost_limit_usd por defecto es 5.0 — 95% de eso.
    await _seed_interaction(
        institution.id,
        teacher.id,
        task="progressive_hint",
        model="groq/llama-3.1-8b-instant",
        cost_usd="4.75",
    )

    resp = await client.get("/observability/ai/usage", headers=auth_headers(teacher_access))
    assert resp.status_code == 200, resp.text
    assert resp.json()["budget"]["level"] == "critical"
