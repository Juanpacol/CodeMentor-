"""Per-student daily token budget (§9.1 "control de costos"), tracked in
Redis so it works the same whether one API instance or many are running
(RE-01 stateless backend) — a local in-process counter would reset per
instance and undercount."""

from datetime import UTC, datetime

from redis.asyncio import Redis

from logica.config import get_settings
from logica.core.errors import ConflictError


def _budget_key(student_id: str) -> str:
    today = datetime.now(UTC).date().isoformat()
    return f"ai_budget:{student_id}:{today}"


async def get_tokens_used_today(redis: Redis, student_id: str) -> int:
    raw = await redis.get(_budget_key(student_id))
    return int(raw) if raw else 0


async def check_budget(redis: Redis, student_id: str) -> None:
    settings = get_settings()
    used = await get_tokens_used_today(redis, student_id)
    if used >= settings.ai_daily_token_budget_per_student:
        raise ConflictError(
            "Alcanzaste el límite diario de uso del asistente de IA. "
            "Puedes seguir practicando sin ayuda del asistente, o intenta de nuevo mañana."
        )


async def record_usage(redis: Redis, student_id: str, tokens: int) -> None:
    key = _budget_key(student_id)
    # Expire after ~2 days: comfortably past midnight in any timezone, so the
    # counter never leaks into the next day's budget.
    await redis.incrby(key, tokens)
    await redis.expire(key, 60 * 60 * 48)
