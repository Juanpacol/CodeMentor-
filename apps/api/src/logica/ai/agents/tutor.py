"""Agente Tutor (§9.2): progressive hints for a student stuck on an
exercise. Never reveals the full solution (RF-31, enforced twice — by the
prompt's own instructions and by the harness's output guardrail) and always
clearly labeled as AI to the student (RF-35) via a dedicated chat history
distinct from anything a human teacher writes."""

import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.config_service import ensure_agent_enabled
from logica.ai.agents.models import AgentName, TutorMessage, TutorMessageRole
from logica.ai.agents.repository import create_tutor_message, list_tutor_messages
from logica.ai.skills.progressive_hint import generate_progressive_hint
from logica.ai.skills.retrieve_context import retrieve_context
from logica.core.errors import NotFoundError, PermissionDeniedError
from logica.modules.content.models import TopicGroupStateValue
from logica.modules.content.repository import get_topic, list_topic_group_states_for_group
from logica.modules.exercises.models import Exercise
from logica.modules.exercises.repository import get_exercise, list_topic_ids_for_exercise
from logica.modules.groups.service import get_group_with_access
from logica.modules.users.models import Role, User


async def _get_enabled_exercise(
    db: AsyncSession, institution_id: uuid.UUID, group_id: uuid.UUID, exercise_id: uuid.UUID
) -> Exercise:
    exercise = await get_exercise(db, exercise_id)
    if exercise is None or exercise.institution_id != institution_id:
        raise NotFoundError("Ejercicio no encontrado")

    topic_ids = await list_topic_ids_for_exercise(db, exercise_id)
    states = await list_topic_group_states_for_group(db, group_id)
    enabled_topic_ids = {s.topic_id for s in states if s.state == TopicGroupStateValue.enabled}
    if not any(tid in enabled_topic_ids for tid in topic_ids):
        raise PermissionDeniedError("Este ejercicio no está habilitado para tu grupo")
    return exercise


async def ask_hint(
    db: AsyncSession,
    redis: Redis,
    student: User,
    *,
    group_id: uuid.UUID,
    exercise_id: uuid.UUID,
    attempt_number: int,
    student_answer: str,
) -> TutorMessage:
    if student.role != Role.student:
        raise PermissionDeniedError("Solo un estudiante puede pedir una pista al tutor")

    await get_group_with_access(db, student, group_id)
    await ensure_agent_enabled(db, group_id, AgentName.tutor)

    exercise = await _get_enabled_exercise(db, student.institution_id, group_id, exercise_id)

    topic_ids = await list_topic_ids_for_exercise(db, exercise_id)
    topic_name = "este tema"
    if topic_ids:
        topic = await get_topic(db, topic_ids[0])
        if topic is not None:
            topic_name = topic.name

    reference_context = await retrieve_context(
        db,
        student.institution_id,
        exercise.content.get("statement", exercise.title),
        topic_id=topic_ids[0] if topic_ids else None,
    )

    await create_tutor_message(
        db,
        TutorMessage(
            institution_id=student.institution_id,
            group_id=group_id,
            student_id=student.id,
            exercise_id=exercise_id,
            role=TutorMessageRole.student,
            content=student_answer,
        ),
    )

    hint_text = await generate_progressive_hint(
        db,
        redis,
        student,
        language=exercise.content.get("language", ""),
        topic_name=topic_name,
        statement=exercise.content.get("statement", exercise.title),
        attempt_number=attempt_number,
        student_answer=student_answer,
        reference_context=reference_context,
    )

    return await create_tutor_message(
        db,
        TutorMessage(
            institution_id=student.institution_id,
            group_id=group_id,
            student_id=student.id,
            exercise_id=exercise_id,
            role=TutorMessageRole.tutor,
            content=hint_text,
        ),
    )


async def get_history(
    db: AsyncSession,
    user: User,
    *,
    group_id: uuid.UUID,
    exercise_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
) -> list[TutorMessage]:
    await get_group_with_access(db, user, group_id)

    if user.role == Role.student:
        if student_id is not None and student_id != user.id:
            raise PermissionDeniedError("No puedes ver el historial de otro estudiante")
        target_student_id = user.id
    else:
        if student_id is None:
            raise PermissionDeniedError("Debes indicar de qué estudiante quieres ver el historial")
        target_student_id = student_id

    return await list_tutor_messages(db, group_id, target_student_id, exercise_id)
