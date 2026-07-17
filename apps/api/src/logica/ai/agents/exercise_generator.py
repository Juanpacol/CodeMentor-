"""Agente Generador de ejercicios (§9.2, RF-32): proposes a new exercise for
a topic/level/type, grounded in the course's own RAG material and existing
similar exercises so it doesn't duplicate the bank. Every output lands as
`status=draft, origin=ai` — invisible to students until a teacher reviews
and publishes it (via the existing PATCH /exercises/{id})."""

import uuid
from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.config_service import ensure_agent_enabled
from logica.ai.agents.models import AgentName
from logica.ai.harness.structured import complete_structured
from logica.ai.skills.retrieve_context import retrieve_context
from logica.core.errors import NotFoundError, PermissionDeniedError
from logica.modules.content.repository import get_language, get_topic
from logica.modules.exercises.models import Exercise, ExerciseOrigin, ExerciseStatus, ExerciseType
from logica.modules.exercises.repository import list_exercises
from logica.modules.groups.service import get_group_with_access
from logica.modules.users.models import Role, User

_SCHEMA_HINTS: dict[ExerciseType, str] = {
    ExerciseType.true_false: '{"title": "...", "content": {"statement": "...", "answer": true}}',
    ExerciseType.multiple_choice: (
        '{"title": "...", "content": {"statement": "...", "options": ["...", "..."], '
        '"answer_index": 0}}'
    ),
    ExerciseType.fill_code: (
        '{"title": "...", "content": {"statement": "...", "code_template": "...", '
        '"blanks": ["...", "..."]}}'
    ),
    ExerciseType.find_error: (
        '{"title": "...", "content": {"statement": "...", "code": "...", "error_line": 1, '
        '"error_kind": "sintaxis"}}'
    ),
    ExerciseType.trace_variables: (
        '{"title": "...", "content": {"statement": "...", "code": "...", '
        '"expected_trace": [{"variable": "valor"}]}}'
    ),
    ExerciseType.order_lines: (
        '{"title": "...", "content": {"statement": "...", "lines": ["...", "..."], '
        '"correct_order": [0, 1]}}'
    ),
    ExerciseType.argued_response: '{"title": "...", "content": {"prompt": "..."}}',
    ExerciseType.live_code: (
        '{"title": "...", "content": {"language": "python", "version": "3.10.0", '
        '"starter_code": "...", "test_cases": [{"stdin": "...", "expected_stdout": "..."}]}}'
    ),
}


class ExerciseGenerationOutput(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: dict[str, Any]


async def generate_exercise_draft(
    db: AsyncSession,
    redis: Redis,
    teacher: User,
    *,
    group_id: uuid.UUID,
    topic_id: uuid.UUID,
    exercise_type: ExerciseType,
) -> Exercise:
    if teacher.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede generar ejercicios")

    await get_group_with_access(db, teacher, group_id)
    await ensure_agent_enabled(db, group_id, AgentName.exercise_generator)

    topic = await get_topic(db, topic_id)
    if topic is None or topic.institution_id != teacher.institution_id:
        raise NotFoundError("Tema no encontrado")
    language = await get_language(db, topic.language_id)
    if language is None:
        raise NotFoundError("Lenguaje no encontrado")

    reference_context = await retrieve_context(
        db, teacher.institution_id, f"{topic.name} {exercise_type.value}"
    )
    existing = await list_exercises(db, teacher.institution_id, topic_id=topic_id)
    similar_exercises = "\n".join(f"- {e.title}" for e in existing[:5])

    output = await complete_structured(
        db,
        redis,
        task="exercise_generation",
        user=teacher,
        template_vars={
            "exercise_type": exercise_type.value,
            "topic_name": topic.name,
            "language": language.name,
            "level": topic.level.value,
            "reference_context": reference_context,
            "similar_exercises": similar_exercises,
            "schema_hint": _SCHEMA_HINTS[exercise_type],
        },
        output_model=ExerciseGenerationOutput,
    )

    exercise = Exercise(
        institution_id=teacher.institution_id,
        language_id=topic.language_id,
        created_by_id=teacher.id,
        title=output.title,
        type=exercise_type,
        content=output.content,
        origin=ExerciseOrigin.ai,
        status=ExerciseStatus.draft,
    )
    db.add(exercise)
    await db.flush()
    await db.refresh(exercise)
    return exercise
