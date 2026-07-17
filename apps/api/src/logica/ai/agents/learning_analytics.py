"""Agente de analítica de aprendizaje (§9.2): detects patterns in a group's
practice activity and hands the teacher a short summary. Purely informative
— never touches grades or content on its own."""

import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.config_service import ensure_agent_enabled
from logica.ai.agents.models import AgentName
from logica.ai.skills.summarize_group import generate_group_summary
from logica.core.errors import NotFoundError, PermissionDeniedError
from logica.modules.evaluations.models import PracticeSubmission
from logica.modules.exercises.models import Exercise, ExerciseType
from logica.modules.groups.repository import get_group
from logica.modules.groups.service import get_group_with_access
from logica.modules.users.models import Role, User


async def _practice_stats(db: AsyncSession, group_id: uuid.UUID) -> dict[str, Any]:
    total_stmt = select(func.count(PracticeSubmission.id)).where(
        PracticeSubmission.group_id == group_id
    )
    total = (await db.execute(total_stmt)).scalar_one()

    correct_stmt = select(func.count(PracticeSubmission.id)).where(
        PracticeSubmission.group_id == group_id, PracticeSubmission.correct.is_(True)
    )
    correct = (await db.execute(correct_stmt)).scalar_one()

    by_type_total_stmt = (
        select(Exercise.type, func.count(PracticeSubmission.id))
        .join(Exercise, Exercise.id == PracticeSubmission.exercise_id)
        .where(PracticeSubmission.group_id == group_id)
        .group_by(Exercise.type)
    )
    by_type_correct_stmt = (
        select(Exercise.type, func.count(PracticeSubmission.id))
        .join(Exercise, Exercise.id == PracticeSubmission.exercise_id)
        .where(PracticeSubmission.group_id == group_id, PracticeSubmission.correct.is_(True))
        .group_by(Exercise.type)
    )
    totals_by_type: dict[ExerciseType, int] = dict(
        (await db.execute(by_type_total_stmt)).tuples().all()
    )
    correct_by_type: dict[ExerciseType, int] = dict(
        (await db.execute(by_type_correct_stmt)).tuples().all()
    )

    accuracy_by_type = {
        exercise_type.value: round(correct_by_type.get(exercise_type, 0) / count, 2)
        for exercise_type, count in totals_by_type.items()
        if count > 0
    }

    return {
        "total_submissions": total,
        "accuracy_overall": round(correct / total, 2) if total else None,
        "accuracy_by_exercise_type": accuracy_by_type,
    }


async def summarize_group(
    db: AsyncSession, redis: Redis, teacher: User, *, group_id: uuid.UUID
) -> str:
    if teacher.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError(
            "Solo un docente o administrador puede pedir un resumen del grupo"
        )

    await get_group_with_access(db, teacher, group_id)
    await ensure_agent_enabled(db, group_id, AgentName.learning_analytics)

    group = await get_group(db, group_id)
    if group is None:
        raise NotFoundError("Grupo no encontrado")

    stats = await _practice_stats(db, group_id)
    return await generate_group_summary(db, redis, teacher, group_name=group.name, stats=stats)
