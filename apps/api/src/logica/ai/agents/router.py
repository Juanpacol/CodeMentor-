import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents import (
    code_integrity,
    config_service,
    exercise_generator,
    grading_assistant,
    learning_analytics,
    pending_approvals,
    tutor,
)
from logica.ai.agents.models import AgentName
from logica.ai.agents.repository import list_alerts_for_evaluation
from logica.ai.agents.schemas import (
    AgentConfigOut,
    AgentToggleRequest,
    ExerciseGenerateRequest,
    GradingSuggestionOut,
    GradingSuggestionRequest,
    GroupSummaryOut,
    GuideExercisesRequest,
    IntegrityAlertOut,
    IntegrityCheckRequest,
    PendingApprovalsOut,
    PendingExerciseOut,
    PendingGradingSuggestionOut,
    TutorHintRequest,
    TutorMessageOut,
)
from logica.core.arq_dep import get_arq_pool
from logica.core.errors import NotFoundError
from logica.core.rate_limit import user_limiter
from logica.core.redis_dep import get_redis
from logica.core.security import get_current_user
from logica.db import get_db
from logica.modules.evaluations.repository import get_evaluation
from logica.modules.exercises.schemas import ExerciseOut
from logica.modules.groups.service import get_group_with_access
from logica.modules.guides import service as guides_service
from logica.modules.guides.models import Guide
from logica.modules.guides.schemas import GuideGenerateRequest, GuideOut
from logica.modules.users.models import User

router = APIRouter(prefix="/ai", tags=["ai-agents"])


@router.get("/groups/{group_id}/agents", response_model=list[AgentConfigOut])
async def list_agents(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentConfigOut]:
    statuses = await config_service.list_agent_status(db, user, group_id)
    return [AgentConfigOut(agent_name=name, enabled=enabled) for name, enabled in statuses.items()]


@router.put("/groups/{group_id}/agents/{agent_name}", response_model=AgentConfigOut)
async def toggle_agent(
    group_id: uuid.UUID,
    agent_name: AgentName,
    payload: AgentToggleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentConfigOut:
    config = await config_service.set_agent_enabled(db, user, group_id, agent_name, payload.enabled)
    await db.commit()
    return AgentConfigOut(agent_name=config.agent_name, enabled=config.enabled)


@router.post("/tutor/hint", response_model=TutorMessageOut, status_code=201)
@user_limiter.limit("30/minute")
async def ask_tutor_hint(
    request: Request,
    payload: TutorHintRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TutorMessageOut:
    message = await tutor.ask_hint(
        db,
        redis,
        user,
        group_id=payload.group_id,
        exercise_id=payload.exercise_id,
        attempt_number=payload.attempt_number,
        student_answer=payload.student_answer,
    )
    await db.commit()
    return TutorMessageOut.model_validate(message)


@router.get("/tutor/history", response_model=list[TutorMessageOut])
async def get_tutor_history(
    group_id: uuid.UUID,
    exercise_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TutorMessageOut]:
    messages = await tutor.get_history(
        db, user, group_id=group_id, exercise_id=exercise_id, student_id=student_id
    )
    return [TutorMessageOut.model_validate(m) for m in messages]


@router.post("/exercises/generate", response_model=ExerciseOut, status_code=201)
@user_limiter.limit("20/minute")
async def generate_exercise(
    request: Request,
    payload: ExerciseGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ExerciseOut:
    exercise = await exercise_generator.generate_exercise_draft(
        db,
        redis,
        user,
        group_id=payload.group_id,
        topic_id=payload.topic_id,
        exercise_type=payload.exercise_type,
    )
    await db.commit()
    return ExerciseOut.model_validate(exercise)


@router.post("/guides/generate", response_model=GuideOut, status_code=202)
@user_limiter.limit("20/minute")
async def generate_guide(
    request: Request,
    payload: GuideGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> Guide:
    """202 y no 201: devuelve la guía en `status=generating` y el worker la
    completa. Generar son N llamadas al modelo (una por sección) con 30 s de
    timeout cada una — en el request path se pasaría del límite de Render.
    El cliente hace polling sobre `GET /guides/{id}`."""
    guide = await guides_service.request_guide_generation(
        db,
        arq_pool,
        user,
        folder_id=payload.folder_id,
        template_id=payload.template_id,
        topic_id=payload.topic_id,
    )
    await db.commit()
    return guide


@router.post("/guides/{guide_id}/exercises", status_code=202)
async def generate_exercises_for_guide(
    guide_id: uuid.UUID,
    payload: GuideExercisesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> dict[str, str]:
    """202: un ejercicio por tipo pedido son N llamadas al modelo, igual que la
    guía. No hay fila de job — los borradores aparecen en el banco a medida que
    el worker los crea, y el cliente los descubre listando por `guide_id`.

    Se valida el acceso acá y no solo en el worker para que un docente que no
    administra el grupo reciba un 403 inmediato en vez de un job silencioso."""
    await guides_service.get_guide_for_teacher(db, user, guide_id)
    await arq_pool.enqueue_job(
        "generate_exercises_for_guide_job",
        str(guide_id),
        [t.value for t in payload.exercise_types],
    )
    return {"status": "encolado"}


@router.post("/grading/suggest", response_model=GradingSuggestionOut)
@user_limiter.limit("30/minute")
async def suggest_grading(
    request: Request,
    payload: GradingSuggestionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> GradingSuggestionOut:
    answer = await grading_assistant.suggest_grade(
        db,
        redis,
        user,
        evaluation_id=payload.evaluation_id,
        answer_id=payload.answer_id,
        rubric=payload.rubric,
    )
    await db.commit()
    return GradingSuggestionOut(
        answer_id=answer.id,
        ai_suggested_score=answer.ai_suggested_score,
        ai_suggested_justification=answer.ai_suggested_justification,
    )


@router.post("/groups/{group_id}/analytics/summary", response_model=GroupSummaryOut)
async def get_group_summary(
    group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> GroupSummaryOut:
    summary = await learning_analytics.summarize_group(db, redis, user, group_id=group_id)
    await db.commit()
    return GroupSummaryOut(summary=summary)


@router.post("/integrity/check", response_model=IntegrityAlertOut)
@user_limiter.limit("30/minute")
async def check_code_integrity(
    request: Request,
    payload: IntegrityCheckRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> IntegrityAlertOut:
    alert = await code_integrity.check_integrity(
        db,
        redis,
        user,
        evaluation_id=payload.evaluation_id,
        answer_id=payload.answer_id,
    )
    await db.commit()
    return IntegrityAlertOut.model_validate(alert)


@router.get("/evaluations/{evaluation_id}/integrity-alerts", response_model=list[IntegrityAlertOut])
async def list_integrity_alerts(
    evaluation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrityAlertOut]:
    evaluation = await get_evaluation(db, evaluation_id)
    if evaluation is None or evaluation.institution_id != user.institution_id:
        raise NotFoundError("Evaluación no encontrada")
    await get_group_with_access(db, user, evaluation.group_id)

    alerts = await list_alerts_for_evaluation(db, evaluation_id)
    return [IntegrityAlertOut.model_validate(a) for a in alerts]


@router.get("/pending-approvals", response_model=PendingApprovalsOut)
async def get_pending_approvals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PendingApprovalsOut:
    exercises, suggestions, guides = await pending_approvals.list_pending_approvals(db, user)
    return PendingApprovalsOut(
        exercises=[PendingExerciseOut.model_validate(e) for e in exercises],
        guides=[GuideOut.model_validate(g) for g in guides],
        grading_suggestions=[
            PendingGradingSuggestionOut(
                answer_id=s.answer.id,
                evaluation_id=s.evaluation_id,
                exercise_title=s.exercise_title,
                ai_suggested_score=s.answer.ai_suggested_score,
                ai_suggested_justification=s.answer.ai_suggested_justification,
            )
            for s in suggestions
        ],
    )
