import uuid
from typing import Any

from sqlalchemy import select
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
