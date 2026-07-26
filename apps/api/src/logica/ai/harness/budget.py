"""Per-user daily token budget (§9.1 "control de costos"), tracked in
Redis so it works the same whether one API instance or many are running
(RE-01 stateless backend) — a local in-process counter would reset per
instance and undercount.

El tope depende del rol (Fase 16): un docente consume en una sola acción lo que
un estudiante en un día — generar una guía son N llamadas al modelo, una por
sección. Con un tope único, la primera guía se rechazaría por presupuesto."""

from datetime import UTC, datetime

from redis.asyncio import Redis

from logica.config import get_settings
from logica.core.errors import ConflictError
from logica.modules.users.models import Role


def _budget_key(user_id: str) -> str:
    today = datetime.now(UTC).date().isoformat()
    return f"ai_budget:{user_id}:{today}"


def daily_limit_for(role: Role) -> int:
    settings = get_settings()
    if role in (Role.teacher, Role.admin):
        return settings.ai_daily_token_budget_per_teacher
    return settings.ai_daily_token_budget_per_student


async def get_tokens_used_today(redis: Redis, user_id: str) -> int:
    raw = await redis.get(_budget_key(user_id))
    return int(raw) if raw else 0


async def check_budget(redis: Redis, user_id: str, role: Role = Role.student) -> None:
    """`role` tiene default `student` (el tope más estricto) a propósito: si un
    llamador nuevo se olvida de pasarlo, falla cerrado — se corta antes de gastar
    — en vez de otorgar el cupo de docente por omisión."""
    used = await get_tokens_used_today(redis, user_id)
    if used >= daily_limit_for(role):
        raise ConflictError(
            "Alcanzaste el límite diario de uso del asistente de IA. "
            "Puedes seguir practicando sin ayuda del asistente, o intenta de nuevo mañana."
        )


async def record_usage(redis: Redis, user_id: str, tokens: int) -> None:
    key = _budget_key(user_id)
    # Expire after ~2 days: comfortably past midnight in any timezone, so the
    # counter never leaks into the next day's budget.
    await redis.incrby(key, tokens)
    await redis.expire(key, 60 * 60 * 48)
