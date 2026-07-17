"""Agente de integridad de código (§9.2): a supporting signal for a teacher
reviewing a `live_code` submission — never an automatic sanction. Combines a
cheap heuristic (submission speed relative to attempt start) with an LLM
opinion, both surfaced together so the teacher can judge for themselves."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.config_service import ensure_agent_enabled
from logica.ai.agents.models import AgentName, CodeIntegrityAlert
from logica.ai.agents.repository import create_code_integrity_alert
from logica.ai.harness.structured import complete_structured
from logica.core.errors import NotFoundError, PermissionDeniedError, ValidationDomainError
from logica.modules.evaluations.repository import (
    get_answer_by_id,
    get_attempt_by_id,
    get_evaluation,
    get_evaluation_exercise,
)
from logica.modules.exercises.models import ExerciseType
from logica.modules.exercises.repository import get_exercise
from logica.modules.groups.service import get_group_with_access
from logica.modules.users.models import Role, User

# Below this, a submission is flagged as suspiciously fast for a live-code
# exercise — a heuristic signal fed to the model, never a verdict on its own.
_FAST_SUBMISSION_SECONDS = 20


class IntegrityCheckOutput(BaseModel):
    suspicious: bool
    reasoning: str = Field(min_length=1)


async def check_integrity(
    db: AsyncSession,
    redis: Redis,
    teacher: User,
    *,
    evaluation_id: uuid.UUID,
    answer_id: uuid.UUID,
) -> CodeIntegrityAlert:
    if teacher.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError(
            "Solo un docente o administrador puede pedir un chequeo de integridad"
        )

    evaluation = await get_evaluation(db, evaluation_id)
    if evaluation is None or evaluation.institution_id != teacher.institution_id:
        raise NotFoundError("Evaluación no encontrada")
    await get_group_with_access(db, teacher, evaluation.group_id)
    await ensure_agent_enabled(db, evaluation.group_id, AgentName.code_integrity)

    answer = await get_answer_by_id(db, answer_id)
    if answer is None:
        raise NotFoundError("Respuesta no encontrada")
    eval_exercise = await get_evaluation_exercise(db, answer.evaluation_exercise_id)
    if eval_exercise is None or eval_exercise.evaluation_id != evaluation_id:
        raise NotFoundError("Respuesta no encontrada en esta evaluación")

    exercise = await get_exercise(db, eval_exercise.exercise_id)
    if exercise is None or exercise.type != ExerciseType.live_code:
        raise ValidationDomainError(
            "El chequeo de integridad solo aplica a retos de código en vivo"
        )

    attempt = await get_attempt_by_id(db, answer.attempt_id)
    if attempt is None:
        raise NotFoundError("Intento no encontrado")

    elapsed_seconds = (datetime.now(UTC) - attempt.started_at).total_seconds()
    code = str(answer.answer.get("code", ""))
    is_fast = elapsed_seconds < _FAST_SUBMISSION_SECONDS
    speed_note = "sospechosamente rápido" if is_fast else "normal"
    heuristic_notes = (
        f"Tiempo transcurrido desde el inicio del intento: {elapsed_seconds:.0f}s ({speed_note}). "
        f"Longitud del código: {len(code)} caracteres."
    )

    output = await complete_structured(
        db,
        redis,
        task="code_integrity",
        user=teacher,
        template_vars={
            "statement": exercise.content.get("starter_code", exercise.title),
            "code": code,
            "heuristic_notes": heuristic_notes,
        },
        output_model=IntegrityCheckOutput,
    )

    return await create_code_integrity_alert(
        db,
        CodeIntegrityAlert(
            evaluation_answer_id=answer.id,
            suspicious=output.suspicious,
            reasoning=output.reasoning,
        ),
    )
