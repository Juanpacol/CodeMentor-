"""Skill "resumir progreso de un grupo" (§9.3): the Learning Analytics agent
is a thin caller of this — the aggregation query lives in the agent module
(it needs evaluations/practice-submission repositories), this skill only
turns already-aggregated stats into readable prose."""

import json
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.harness.harness import complete_task
from logica.modules.users.models import User


async def generate_group_summary(
    db: AsyncSession, redis: Redis, user: User, *, group_name: str, stats: dict[str, Any]
) -> str:
    result = await complete_task(
        db,
        redis,
        task="summarize_group",
        user=user,
        template_vars={
            "group_name": group_name,
            "stats_json": json.dumps(stats, ensure_ascii=False),
        },
    )
    return result.text
