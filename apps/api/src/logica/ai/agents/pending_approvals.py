"""Bandeja unificada de aprobación (§9.6): AI-generated exercises still in
`draft` and grading suggestions still awaiting a teacher's confirmation,
combined in one place instead of scattered per module — matching the "una
sola cola en lugar de buscar en cada módulo" requirement."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import PermissionDeniedError
from logica.modules.evaluations.models import Evaluation, EvaluationAnswer, EvaluationExercise
from logica.modules.exercises.models import Exercise, ExerciseOrigin, ExerciseStatus
from logica.modules.users.models import Role, User


@dataclass(frozen=True)
class PendingGradingSuggestion:
    answer: EvaluationAnswer
    evaluation_id: uuid.UUID
    exercise_title: str


async def _list_pending_exercises(db: AsyncSession, institution_id: uuid.UUID) -> list[Exercise]:
    stmt = select(Exercise).where(
        Exercise.institution_id == institution_id,
        Exercise.origin == ExerciseOrigin.ai,
        Exercise.status == ExerciseStatus.draft,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _list_pending_grading_suggestions(
    db: AsyncSession, institution_id: uuid.UUID
) -> list[PendingGradingSuggestion]:
    stmt = (
        select(EvaluationAnswer, EvaluationExercise.evaluation_id, Exercise.title)
        .join(EvaluationExercise, EvaluationExercise.id == EvaluationAnswer.evaluation_exercise_id)
        .join(Evaluation, Evaluation.id == EvaluationExercise.evaluation_id)
        .join(Exercise, Exercise.id == EvaluationExercise.exercise_id)
        .where(
            Evaluation.institution_id == institution_id,
            EvaluationAnswer.ai_suggested_score.is_not(None),
            EvaluationAnswer.manual_score.is_(None),
        )
    )
    result = await db.execute(stmt)
    return [
        PendingGradingSuggestion(answer=answer, evaluation_id=evaluation_id, exercise_title=title)
        for answer, evaluation_id, title in result.all()
    ]


async def list_pending_approvals(
    db: AsyncSession, teacher: User
) -> tuple[list[Exercise], list[PendingGradingSuggestion]]:
    if teacher.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede ver esta bandeja")

    exercises = await _list_pending_exercises(db, teacher.institution_id)
    suggestions = await _list_pending_grading_suggestions(db, teacher.institution_id)
    return exercises, suggestions
