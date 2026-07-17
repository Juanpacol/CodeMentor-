"""Skill "redactar retroalimentación pedagógica" (§9.3): turns a technical
grading result into a respectful, plain-Spanish explanation for a teenager.
Not wired into the grading engine's request path yet (that stays purely
synchronous per RE-05/ADR-002) — available for the Tutor or a future
"explain my result" endpoint to call on demand."""

from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.harness.harness import complete_task
from logica.modules.users.models import User


async def generate_pedagogical_feedback(
    db: AsyncSession,
    redis: Redis,
    user: User,
    *,
    statement: str,
    correct: bool,
    detail: dict[str, Any],
    error_line: int | None = None,
) -> str:
    result = await complete_task(
        db,
        redis,
        task="pedagogical_feedback",
        user=user,
        template_vars={
            "statement": statement,
            "correct": correct,
            "error_line": error_line,
            "detail": detail,
        },
    )
    return result.text
