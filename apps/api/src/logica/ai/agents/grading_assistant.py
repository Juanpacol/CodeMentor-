"""Agente Asistente de calificación (§9.2, RF-33): suggests a score and
justification for an open-ended ("respuesta argumentada") answer, based on
the teacher's own rubric. Writes only to `ai_suggested_score`/
`ai_suggested_justification` — never to `score`/`manual_score` — so a grade
only ever changes when a teacher confirms it via the pre-existing
`evaluations.service.submit_manual_review()`."""

import uuid

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.config_service import ensure_agent_enabled
from logica.ai.agents.models import AgentName
from logica.ai.harness.structured import complete_structured
from logica.core.errors import NotFoundError, PermissionDeniedError
from logica.modules.evaluations.models import EvaluationAnswer
from logica.modules.evaluations.repository import (
    get_answer_by_id,
    get_evaluation,
    get_evaluation_exercise,
)
from logica.modules.exercises.repository import get_exercise
from logica.modules.groups.service import get_group_with_access
from logica.modules.users.models import Role, User


class GradingSuggestionOutput(BaseModel):
    suggested_score: float = Field(ge=0.0, le=1.0)
    justification: str = Field(min_length=1)


async def suggest_grade(
    db: AsyncSession,
    redis: Redis,
    teacher: User,
    *,
    evaluation_id: uuid.UUID,
    answer_id: uuid.UUID,
    rubric: str,
) -> EvaluationAnswer:
    if teacher.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError(
            "Solo un docente o administrador puede pedir una sugerencia de calificación"
        )

    evaluation = await get_evaluation(db, evaluation_id)
    if evaluation is None or evaluation.institution_id != teacher.institution_id:
        raise NotFoundError("Evaluación no encontrada")
    await get_group_with_access(db, teacher, evaluation.group_id)
    await ensure_agent_enabled(db, evaluation.group_id, AgentName.grading_assistant)

    answer = await get_answer_by_id(db, answer_id)
    if answer is None:
        raise NotFoundError("Respuesta no encontrada")
    eval_exercise = await get_evaluation_exercise(db, answer.evaluation_exercise_id)
    if eval_exercise is None or eval_exercise.evaluation_id != evaluation_id:
        raise NotFoundError("Respuesta no encontrada en esta evaluación")

    exercise = await get_exercise(db, eval_exercise.exercise_id)
    if exercise is None:
        raise NotFoundError("Ejercicio no encontrado")

    output = await complete_structured(
        db,
        redis,
        task="grading_suggestion",
        user=teacher,
        template_vars={
            "rubric": rubric,
            "statement": exercise.content.get("prompt", exercise.title),
            "student_answer": answer.answer.get("text", ""),
        },
        output_model=GradingSuggestionOutput,
    )

    answer.ai_suggested_score = output.suggested_score
    answer.ai_suggested_justification = output.justification
    await db.flush()
    await db.refresh(answer)
    return answer
