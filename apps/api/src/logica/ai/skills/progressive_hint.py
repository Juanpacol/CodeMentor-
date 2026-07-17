"""Skill "generar pista progresiva" (§9.3): the same implementation the
Tutor agent uses is reusable by anything else that needs a hint (MCP server,
Fase 7) — one implementation, several consumers, matching the "plugin"
principle already used for exercise types (RE-05)."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.harness.harness import complete_task
from logica.modules.users.models import User


async def generate_progressive_hint(
    db: AsyncSession,
    redis: Redis,
    user: User,
    *,
    language: str,
    topic_name: str,
    statement: str,
    attempt_number: int,
    student_answer: str,
    reference_context: str = "",
    forbid_full_solution: bool = True,
) -> str:
    result = await complete_task(
        db,
        redis,
        task="progressive_hint",
        user=user,
        template_vars={
            "language": language,
            "topic_name": topic_name,
            "statement": statement,
            "attempt_number": attempt_number,
            "student_answer": student_answer,
            "reference_context": reference_context,
        },
        untrusted_input=student_answer,
        forbid_full_solution=forbid_full_solution,
    )
    return result.text
