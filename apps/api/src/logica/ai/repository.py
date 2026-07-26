import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.models import AiInteraction

_SUMMARY_MAX_LEN = 500


async def record_interaction(
    db: AsyncSession,
    *,
    institution_id: uuid.UUID,
    user_id: uuid.UUID,
    task: str,
    model: str,
    response_text: str,
    prompt_tokens: int,
    completion_tokens: int,
    from_cache: bool,
    blocked_by_guardrail: bool = False,
    extra: dict[str, Any] | None = None,
    prompt_version: int = 1,
    cost_usd: Decimal = Decimal("0"),
) -> AiInteraction:
    entry = AiInteraction(
        institution_id=institution_id,
        user_id=user_id,
        task=task,
        model=model,
        response_summary=response_text[:_SUMMARY_MAX_LEN],
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        from_cache=from_cache,
        blocked_by_guardrail=blocked_by_guardrail,
        extra=extra or {},
        prompt_version=prompt_version,
        cost_usd=cost_usd,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_interaction(db: AsyncSession, interaction_id: uuid.UUID) -> AiInteraction | None:
    return await db.get(AiInteraction, interaction_id)


async def list_interactions_for_user(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[AiInteraction]:
    stmt = (
        select(AiInteraction)
        .where(AiInteraction.user_id == user_id)
        .order_by(AiInteraction.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --- Ítem 14: dashboard de costo. Vive acá (no en un ai/analytics/ nuevo)
# porque este módulo ya es dueño de todas las queries de AiInteraction —
# agregar un paquete nuevo para 2 funciones más sería la abstracción
# prematura que este repo evita. ---


@dataclass(frozen=True)
class AiUsageRow:
    key: str
    interactions: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal
    cache_hits: int
    blocked: int


GroupBy = Literal["task", "model", "day"]


async def summarize_usage(
    db: AsyncSession,
    institution_id: uuid.UUID,
    *,
    date_from: date,
    date_to: date,
    group_by: GroupBy,
) -> list[AiUsageRow]:
    """Claves de agrupación acotadas (7 tareas, ~5 modelos, <=31 días) — este
    resumen no necesita paginación, a diferencia de un listado de filas
    crudas. Cota semiabierta en `created_at` (no `<= date_to`) para no perder
    en silencio lo que pasó el último día después de medianoche — el mismo
    bug que `observability.repository.list_error_logs` sí tiene, no se copia
    acá."""
    column = {
        "task": AiInteraction.task,
        "model": AiInteraction.model,
        "day": func.date(AiInteraction.created_at),
    }[group_by]

    stmt: Select[Any] = (
        select(
            column.label("key"),
            func.count().label("interactions"),
            func.coalesce(func.sum(AiInteraction.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AiInteraction.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(AiInteraction.cost_usd), 0).label("cost_usd"),
            func.count().filter(AiInteraction.from_cache.is_(True)).label("cache_hits"),
            func.count().filter(AiInteraction.blocked_by_guardrail.is_(True)).label("blocked"),
        )
        .where(
            AiInteraction.institution_id == institution_id,
            AiInteraction.created_at >= date_from,
            AiInteraction.created_at < date_to + timedelta(days=1),
        )
        .group_by(column)
        .order_by(func.sum(AiInteraction.cost_usd).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        AiUsageRow(
            key=str(row.key),
            interactions=row.interactions,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            cost_usd=Decimal(row.cost_usd),
            cache_hits=row.cache_hits,
            blocked=row.blocked,
        )
        for row in rows
    ]


async def month_to_date_cost(
    db: AsyncSession, institution_id: uuid.UUID, *, today: date
) -> Decimal:
    month_start = today.replace(day=1)
    stmt = select(func.coalesce(func.sum(AiInteraction.cost_usd), 0)).where(
        AiInteraction.institution_id == institution_id,
        AiInteraction.created_at >= month_start,
        AiInteraction.created_at < today + timedelta(days=1),
    )
    total = (await db.execute(stmt)).scalar_one()
    return Decimal(total)
