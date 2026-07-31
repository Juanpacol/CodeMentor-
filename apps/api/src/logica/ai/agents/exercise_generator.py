"""Agente Generador de ejercicios (§9.2, RF-32): proposes a new exercise for
a topic/level/type, grounded in the course's own RAG material and existing
similar exercises so it doesn't duplicate the bank. Every output lands as
`status=draft, origin=ai` — invisible to students until a teacher reviews
and publishes it (via the existing PATCH /exercises/{id})."""

import uuid
from collections.abc import Sequence
from typing import Any

import structlog
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.harness.structured import complete_structured
from logica.ai.skills.retrieve_context import retrieve_context
from logica.core.errors import (
    ConflictError,
    LogicaError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationDomainError,
)
from logica.modules.content.models import Topic
from logica.modules.content.repository import get_language, get_topic
from logica.modules.exercises.models import (
    Exercise,
    ExerciseOrigin,
    ExerciseStatus,
    ExerciseType,
    TopicExercise,
)
from logica.modules.exercises.repository import (
    get_exercise,
    get_topic_exercise_link,
    list_exercises,
    list_topic_ids_for_exercise,
)
from logica.modules.groups.service import get_group_with_access
from logica.modules.guides.models import Guide, GuidesFolder
from logica.modules.users.models import Role, User

logger = structlog.get_logger()

# Cuánto de la guía se le muestra al modelo. La guía completa son varias
# secciones y haría crecer el prompt de cada ejercicio del lote sin aportar:
# lo que importa es la notación y el alcance, que están al principio.
_GUIDE_EXCERPT_CHARS = 1500

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
    ExerciseType.argued_response: '{"title": "...", "content": {"prompt": "..."}}',
    ExerciseType.live_code: (
        '{"title": "...", "content": {"language": "python", "version": "3.10.0", '
        '"starter_code": "...", "test_cases": [{"stdin": "...", "expected_stdout": "..."}]}}'
    ),
}


class ExerciseGenerationOutput(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: dict[str, Any]


async def _complete_exercise(
    db: AsyncSession,
    redis: Redis,
    teacher: User,
    *,
    topic: Topic,
    language_name: str,
    exercise_type: ExerciseType,
    guide_excerpt: str = "",
    extra_similar: Sequence[str] = (),
) -> ExerciseGenerationOutput:
    """Solo la llamada al modelo. Está separada de la persistencia a propósito:
    el lote de la Fase 17 necesita envolver los INSERTs en un SAVEPOINT, y meter
    también esta parte adentro revertiría la fila de `ai_interactions` que
    `complete_structured` ya escribió antes de fallar — justo el registro que
    explica por qué falló.

    `extra_similar` es para el caso de variantes (§ítem 21): además de lo que
    ya hay en el banco, cada variante nueva del lote debe conocer las que ya
    se generaron en esa misma tanda, o el modelo tiende a repetir la primera."""
    reference_context = await retrieve_context(
        db, teacher.institution_id, f"{topic.name} {exercise_type.value}", topic_id=topic.id
    )
    existing = await list_exercises(db, teacher.institution_id, topic_id=topic.id)
    similar_titles = [e.title for e in existing[:5]] + list(extra_similar)
    similar_exercises = "\n".join(f"- {t}" for t in similar_titles)

    return await complete_structured(
        db,
        redis,
        task="exercise_generation",
        user=teacher,
        template_vars={
            "exercise_type": exercise_type.value,
            "topic_name": topic.name,
            "language": language_name,
            "level": topic.level.value,
            "reference_context": reference_context,
            "similar_exercises": similar_exercises,
            "guide_excerpt": guide_excerpt,
            "schema_hint": _SCHEMA_HINTS[exercise_type],
        },
        output_model=ExerciseGenerationOutput,
    )


async def _persist_exercise(
    db: AsyncSession,
    teacher: User,
    output: ExerciseGenerationOutput,
    *,
    topic: Topic,
    exercise_type: ExerciseType,
    guide_id: uuid.UUID | None = None,
) -> Exercise:
    exercise = Exercise(
        institution_id=teacher.institution_id,
        language_id=topic.language_id,
        created_by_id=teacher.id,
        title=output.title,
        type=exercise_type,
        content=output.content,
        origin=ExerciseOrigin.ai,
        status=ExerciseStatus.draft,
        guide_id=guide_id,
    )
    db.add(exercise)
    await db.flush()
    await db.refresh(exercise)

    # El eje de organización por tema sigue siendo `topic_exercises`, también
    # para los ejercicios que nacen de una guía: sin este enlace no aparecerían
    # al filtrar el banco por tema, que es como el docente los busca.
    if await get_topic_exercise_link(db, topic.id, exercise.id) is None:
        db.add(TopicExercise(topic_id=topic.id, exercise_id=exercise.id))
        await db.flush()

    logger.info(
        "exercise_draft_persisted",
        exercise_id=str(exercise.id),
        topic_id=str(topic.id),
        guide_id=str(guide_id) if guide_id else None,
        exercise_type=exercise_type.value,
    )
    return exercise


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

    topic = await get_topic(db, topic_id)
    if topic is None or topic.institution_id != teacher.institution_id:
        raise NotFoundError("Tema no encontrado")
    language = await get_language(db, topic.language_id)
    if language is None:
        raise NotFoundError("Lenguaje no encontrado")

    output = await _complete_exercise(
        db,
        redis,
        teacher,
        topic=topic,
        language_name=language.name,
        exercise_type=exercise_type,
    )
    return await _persist_exercise(db, teacher, output, topic=topic, exercise_type=exercise_type)


async def generate_exercises_for_guide(
    db: AsyncSession,
    redis: Redis,
    teacher: User,
    *,
    guide_id: uuid.UUID,
    exercise_types: Sequence[ExerciseType],
) -> list[Exercise]:
    """Fase 17: un ejercicio por tipo pedido, fundamentado en el texto de la guía.

    Pasar el `content_md` de la guía al prompt (v2, variable `guide_excerpt`) es
    lo que hace que estos sean ejercicios *de esa guía* y no del tema en general:
    evalúan lo que la guía alcanzó a explicar, con su misma notación.

    Misma taxonomía de error que `guide_writer._write_all_sections`: un tipo que
    falla se salta (tres de cuatro ejercicios sirven y cero no), pero presupuesto
    agotado o proveedores caídos se propagan — son condiciones globales, y seguir
    con el siguiente tipo solo repite el mismo fallo más lento."""
    if teacher.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede generar ejercicios")

    guide = await db.get(Guide, guide_id)
    if guide is None or guide.institution_id != teacher.institution_id:
        raise NotFoundError("Guía no encontrada")
    folder = await db.get(GuidesFolder, guide.folder_id)
    if folder is None:
        raise NotFoundError("Carpeta de guías no encontrada")

    topic = await get_topic(db, guide.topic_id)
    if topic is None or topic.institution_id != teacher.institution_id:
        raise NotFoundError("Tema no encontrado")
    language = await get_language(db, topic.language_id)
    if language is None:
        raise NotFoundError("Lenguaje no encontrado")

    excerpt = guide.content_md[:_GUIDE_EXCERPT_CHARS]
    created: list[Exercise] = []

    for exercise_type in exercise_types:
        try:
            output = await _complete_exercise(
                db,
                redis,
                teacher,
                topic=topic,
                language_name=language.name,
                exercise_type=exercise_type,
                guide_excerpt=excerpt,
            )
        except (ConflictError, ServiceUnavailableError):
            logger.warning("exercise_batch_aborted", guide_id=str(guide_id), created=len(created))
            raise
        except LogicaError as exc:
            # Fallo aislado de un tipo, casi siempre StructuredOutputError: el
            # modelo no produjo el JSON que ese tipo de ejercicio exige.
            logger.warning(
                "exercise_batch_item_failed",
                guide_id=str(guide_id),
                exercise_type=exercise_type.value,
                error=str(exc),
            )
            continue

        try:
            # SAVEPOINT solo alrededor de los INSERTs (regla de CLAUDE.md): en
            # Postgres una sentencia fallida aborta toda la transacción abierta,
            # así que sin esto un choque contra la restricción única de
            # `topic_exercises` se llevaría los ejercicios ya creados en el lote.
            async with db.begin_nested():
                exercise = await _persist_exercise(
                    db,
                    teacher,
                    output,
                    topic=topic,
                    exercise_type=exercise_type,
                    guide_id=guide.id,
                )
            created.append(exercise)
        except SQLAlchemyError:
            logger.exception(
                "exercise_batch_item_row_failed",
                guide_id=str(guide_id),
                exercise_type=exercise_type.value,
            )

    logger.info(
        "exercises_for_guide_generated",
        guide_id=str(guide_id),
        requested=len(exercise_types),
        created=len(created),
    )
    return created


async def generate_exercise_variants(
    db: AsyncSession,
    redis: Redis,
    teacher: User,
    *,
    exercise_id: uuid.UUID,
    count: int,
) -> list[ExerciseGenerationOutput]:
    """Ítem 21: N variantes de un ejercicio existente (mismo tipo/tema),
    devueltas como *preview* — nada se persiste acá. El docente las revisa,
    edita si quiere, y solo las que acepta se crean como ejercicios reales
    (vía el `POST /exercises` que ya existe) antes de adjuntarlas a la
    evaluación que está armando.

    Aislamiento de fallos por variante, mismo criterio que
    `generate_exercises_for_guide`: si una del lote falla (casi siempre
    `StructuredOutputError`), las demás igual se devuelven — presupuesto
    agotado o proveedores caídos sí se propagan, porque repetir el resto
    solo repetiría el mismo fallo."""
    if teacher.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede generar variantes")

    exercise = await get_exercise(db, exercise_id)
    if exercise is None or exercise.institution_id != teacher.institution_id:
        raise NotFoundError("Ejercicio no encontrado")

    topic_ids = await list_topic_ids_for_exercise(db, exercise_id)
    if not topic_ids:
        raise ValidationDomainError(
            "Este ejercicio no está asociado a ningún tema",
            hint="Solo se pueden generar variantes de ejercicios que ya están en un tema.",
        )
    topic = await get_topic(db, topic_ids[0])
    if topic is None:
        raise NotFoundError("Tema no encontrado")
    language = await get_language(db, exercise.language_id)
    if language is None:
        raise NotFoundError("Lenguaje no encontrado")

    variants: list[ExerciseGenerationOutput] = []
    similar_so_far = [exercise.title]
    for _ in range(count):
        try:
            output = await _complete_exercise(
                db,
                redis,
                teacher,
                topic=topic,
                language_name=language.name,
                exercise_type=exercise.type,
                extra_similar=similar_so_far,
            )
        except (ConflictError, ServiceUnavailableError):
            logger.warning(
                "exercise_variant_batch_aborted",
                exercise_id=str(exercise_id),
                created=len(variants),
            )
            raise
        except LogicaError as exc:
            logger.warning(
                "exercise_variant_batch_item_failed", exercise_id=str(exercise_id), error=str(exc)
            )
            continue

        variants.append(output)
        similar_so_far.append(output.title)

    logger.info(
        "exercise_variants_generated",
        exercise_id=str(exercise_id),
        requested=count,
        generated=len(variants),
    )
    return variants
