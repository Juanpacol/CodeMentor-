import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationDomainError,
)
from logica.modules.content.models import TopicGroupStateValue
from logica.modules.content.repository import (
    get_topic,
    list_topic_group_states_for_group,
    list_topics,
)
from logica.modules.evaluations.models import (
    AttemptStatus,
    Evaluation,
    EvaluationAnswer,
    EvaluationAttempt,
    EvaluationExercise,
    EvaluationMode,
    PracticeSubmission,
)
from logica.modules.evaluations.repository import (
    get_answer,
    get_answer_by_id,
    get_attempt,
    get_attempt_by_id,
    get_evaluation,
    get_evaluation_exercise,
    list_answers_for_attempt,
    list_answers_for_evaluation,
    list_evaluation_exercises,
    list_pending_manual_review,
)
from logica.modules.exercises.models import Exercise, ExerciseStatus, ExerciseType
from logica.modules.exercises.repository import (
    get_exercise,
    list_exercises,
    list_topic_ids_for_exercise,
)
from logica.modules.grading.live_code import grade_live_code
from logica.modules.grading.registry import grade_exercise
from logica.modules.grading.sanitize import strip_answer_key
from logica.modules.grading.types import GradeResult
from logica.modules.groups.repository import get_membership
from logica.modules.groups.service import get_group_with_access
from logica.modules.users.models import Role, User

# Grace period after the timer runs out — protects against clock skew / a
# submission that was in flight exactly at the deadline (§8.2 "pérdida de
# conexión a mitad de una evaluación").
_LATE_TOLERANCE = timedelta(seconds=30)


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError("Solo un docente o administrador puede gestionar evaluaciones")


async def _grade(exercise: Exercise, answer: dict[str, Any]) -> GradeResult:
    """Dispatches to the sync RF-10 registry, except `live_code` (§4.2) which
    needs a sandbox round trip — see grading/live_code.py."""
    if exercise.type == ExerciseType.live_code:
        return await grade_live_code(exercise.content, answer)
    return grade_exercise(exercise.type, exercise.content, answer)


async def _eligible_topic_ids(
    db: AsyncSession,
    institution_id: uuid.UUID,
    group_id: uuid.UUID,
    mode: EvaluationMode,
    up_to_topic_id: uuid.UUID | None,
) -> set[uuid.UUID]:
    topics = await list_topics(db, institution_id)
    states = {s.topic_id: s for s in await list_topic_group_states_for_group(db, group_id)}
    enabled_topic_ids = {
        topic.id
        for topic in topics
        if states.get(topic.id) and states[topic.id].state == TopicGroupStateValue.enabled
    }

    if mode == EvaluationMode.cumulative:
        return enabled_topic_ids

    if up_to_topic_id is None:
        raise ValidationDomainError("Debes indicar hasta qué tema llega la evaluación")
    up_to_topic = await get_topic(db, up_to_topic_id)
    if up_to_topic is None or up_to_topic.institution_id != institution_id:
        raise NotFoundError("Tema no encontrado")

    topic_order = {topic.id: topic.order_index for topic in topics}
    return {
        topic_id
        for topic_id in enabled_topic_ids
        if topic_order.get(topic_id, -1) <= up_to_topic.order_index
    }


async def create_evaluation(
    db: AsyncSession,
    teacher: User,
    group_id: uuid.UUID,
    title: str,
    mode: EvaluationMode,
    up_to_topic_id: uuid.UUID | None,
    duration_minutes: int | None,
    is_ranked: bool,
    exercise_ids: list[uuid.UUID],
) -> Evaluation:
    _ensure_teacher(teacher)
    await get_group_with_access(db, teacher, group_id)

    eligible_topic_ids = await _eligible_topic_ids(
        db, teacher.institution_id, group_id, mode, up_to_topic_id
    )

    evaluation = Evaluation(
        institution_id=teacher.institution_id,
        group_id=group_id,
        teacher_id=teacher.id,
        title=title,
        mode=mode,
        up_to_topic_id=up_to_topic_id if mode == EvaluationMode.fixed else None,
        duration_minutes=duration_minutes,
        is_ranked=is_ranked,
    )
    db.add(evaluation)
    await db.flush()

    for order_index, exercise_id in enumerate(exercise_ids):
        exercise = await get_exercise(db, exercise_id)
        if exercise is None or exercise.institution_id != teacher.institution_id:
            raise NotFoundError(f"Ejercicio {exercise_id} no encontrado")
        if exercise.status != ExerciseStatus.published:
            raise ValidationDomainError(f"El ejercicio '{exercise.title}' no está publicado")

        topic_ids = await list_topic_ids_for_exercise(db, exercise.id)
        if not any(tid in eligible_topic_ids for tid in topic_ids):
            raise ValidationDomainError(
                f"El ejercicio '{exercise.title}' no pertenece al alcance seleccionado"
            )

        db.add(
            EvaluationExercise(
                evaluation_id=evaluation.id,
                exercise_id=exercise.id,
                order_index=order_index,
                exercise_version_at_attach=exercise.version,
            )
        )

    await db.flush()
    await db.refresh(evaluation)
    return evaluation


async def _get_evaluation_in_institution(
    db: AsyncSession, user: User, evaluation_id: uuid.UUID
) -> Evaluation:
    evaluation = await get_evaluation(db, evaluation_id)
    if evaluation is None or evaluation.institution_id != user.institution_id:
        raise NotFoundError("Evaluación no encontrada")
    return evaluation


def _deadline(evaluation: Evaluation, attempt: EvaluationAttempt) -> datetime | None:
    if evaluation.duration_minutes is None:
        return None
    return attempt.started_at + timedelta(minutes=evaluation.duration_minutes)


async def start_or_get_attempt(
    db: AsyncSession, student: User, evaluation_id: uuid.UUID
) -> tuple[Evaluation, EvaluationAttempt, list[tuple[EvaluationExercise, Exercise]]]:
    if student.role != Role.student:
        raise PermissionDeniedError("Solo un estudiante puede presentar una evaluación")

    evaluation = await _get_evaluation_in_institution(db, student, evaluation_id)
    membership = await get_membership(db, evaluation.group_id, student.id)
    if membership is None:
        raise PermissionDeniedError("No perteneces al grupo de esta evaluación")

    attempt = await get_attempt(db, evaluation_id, student.id)
    if attempt is None:
        attempt = EvaluationAttempt(
            institution_id=student.institution_id,
            evaluation_id=evaluation_id,
            student_id=student.id,
            started_at=datetime.now(UTC),
        )
        db.add(attempt)
        await db.flush()
        await db.refresh(attempt)

    eval_exercises = await list_evaluation_exercises(db, evaluation_id)
    pairs: list[tuple[EvaluationExercise, Exercise]] = []
    for ee in eval_exercises:
        exercise = await get_exercise(db, ee.exercise_id)
        assert exercise is not None
        pairs.append((ee, exercise))

    return evaluation, attempt, pairs


async def submit_answer(
    db: AsyncSession,
    student: User,
    evaluation_id: uuid.UUID,
    evaluation_exercise_id: uuid.UUID,
    answer: dict[str, Any],
) -> EvaluationAnswer:
    evaluation = await _get_evaluation_in_institution(db, student, evaluation_id)
    attempt = await get_attempt(db, evaluation_id, student.id)
    if attempt is None:
        raise NotFoundError("Debes iniciar la evaluación antes de responder")
    if attempt.status != AttemptStatus.in_progress:
        raise ConflictError("La evaluación ya fue finalizada")

    if evaluation.duration_minutes is not None:
        deadline = _deadline(evaluation, attempt)
        assert deadline is not None
        if datetime.now(UTC) > deadline + _LATE_TOLERANCE:
            raise ConflictError("El tiempo de la evaluación expiró")

    eval_exercise = await get_evaluation_exercise(db, evaluation_exercise_id)
    if eval_exercise is None or eval_exercise.evaluation_id != evaluation_id:
        raise NotFoundError("Pregunta no encontrada en esta evaluación")

    exercise = await get_exercise(db, eval_exercise.exercise_id)
    assert exercise is not None
    result = await _grade(exercise, answer)

    existing = await get_answer(db, attempt.id, evaluation_exercise_id)
    if existing is None:
        existing = EvaluationAnswer(
            attempt_id=attempt.id, evaluation_exercise_id=evaluation_exercise_id
        )
        db.add(existing)

    existing.answer = answer
    existing.score = result.score
    existing.correct = result.correct
    existing.needs_manual_review = result.needs_manual_review
    await db.flush()
    return existing


def _weighted_total(
    eval_exercises: list[EvaluationExercise], answers: dict[uuid.UUID, EvaluationAnswer]
) -> float:
    total = 0.0
    for ee in eval_exercises:
        answer = answers.get(ee.id)
        if answer is None:
            continue
        effective_score = answer.manual_score if answer.manual_score is not None else answer.score
        total += effective_score * ee.points
    return total


async def _update_ranking_cache(
    redis: Redis, evaluation_id: uuid.UUID, student_id: uuid.UUID, total_score: float
) -> None:
    await redis.zadd(f"ranking:{evaluation_id}", {str(student_id): total_score})


async def finalize_attempt(
    db: AsyncSession, redis: Redis, student: User, evaluation_id: uuid.UUID
) -> EvaluationAttempt:
    evaluation = await _get_evaluation_in_institution(db, student, evaluation_id)
    attempt = await get_attempt(db, evaluation_id, student.id)
    if attempt is None:
        raise NotFoundError("No has iniciado esta evaluación")

    if attempt.status != AttemptStatus.in_progress:
        return attempt  # idempotent: a double "submit" click never recomputes or errors

    eval_exercises = await list_evaluation_exercises(db, evaluation_id)
    answers = {a.evaluation_exercise_id: a for a in await list_answers_for_attempt(db, attempt.id)}

    now = datetime.now(UTC)
    is_late = (
        evaluation.duration_minutes is not None
        and now > _deadline(evaluation, attempt) + _LATE_TOLERANCE  # type: ignore[operator]
    )

    attempt.total_score = _weighted_total(eval_exercises, answers)
    attempt.status = AttemptStatus.expired if is_late else AttemptStatus.submitted
    attempt.submitted_at = now
    await db.flush()
    await db.refresh(attempt)

    if evaluation.is_ranked and attempt.status == AttemptStatus.submitted:
        await _update_ranking_cache(redis, evaluation_id, student.id, attempt.total_score)

    return attempt


async def get_attempt_result(
    db: AsyncSession, user: User, evaluation_id: uuid.UUID
) -> tuple[EvaluationAttempt, list[EvaluationAnswer], float]:
    await _get_evaluation_in_institution(db, user, evaluation_id)
    attempt = await get_attempt(db, evaluation_id, user.id)
    if attempt is None:
        raise NotFoundError("No has presentado esta evaluación")

    eval_exercises = await list_evaluation_exercises(db, evaluation_id)
    max_score = sum(ee.points for ee in eval_exercises)
    answers = await list_answers_for_attempt(db, attempt.id)
    return attempt, answers, max_score


async def get_ranking(redis: Redis, evaluation_id: uuid.UUID) -> list[tuple[uuid.UUID, float]]:
    raw = await redis.zrevrange(f"ranking:{evaluation_id}", 0, -1, withscores=True)
    return [(uuid.UUID(member), score) for member, score in raw]


async def list_manual_review_queue(
    db: AsyncSession, teacher: User, evaluation_id: uuid.UUID
) -> list[tuple[EvaluationAnswer, EvaluationAttempt, Exercise]]:
    _ensure_teacher(teacher)
    evaluation = await _get_evaluation_in_institution(db, teacher, evaluation_id)
    await get_group_with_access(db, teacher, evaluation.group_id)

    pending = await list_pending_manual_review(db, evaluation_id)
    result: list[tuple[EvaluationAnswer, EvaluationAttempt, Exercise]] = []
    for answer in pending:
        attempt = await get_attempt_by_id(db, answer.attempt_id)
        eval_exercise = await get_evaluation_exercise(db, answer.evaluation_exercise_id)
        assert attempt is not None and eval_exercise is not None
        exercise = await get_exercise(db, eval_exercise.exercise_id)
        assert exercise is not None
        result.append((answer, attempt, exercise))
    return result


async def list_all_answers(
    db: AsyncSession, teacher: User, evaluation_id: uuid.UUID
) -> list[tuple[EvaluationAnswer, uuid.UUID]]:
    """Teacher-facing browse view of every submitted answer (not just those
    awaiting manual review) — e.g. so a teacher can pick a `live_code`
    submission to run through the code-integrity check (§9.2), which has
    nothing to do with `needs_manual_review`."""
    _ensure_teacher(teacher)
    evaluation = await _get_evaluation_in_institution(db, teacher, evaluation_id)
    await get_group_with_access(db, teacher, evaluation.group_id)
    return await list_answers_for_evaluation(db, evaluation_id)


async def submit_manual_review(
    db: AsyncSession, teacher: User, evaluation_id: uuid.UUID, answer_id: uuid.UUID, score: float
) -> EvaluationAnswer:
    _ensure_teacher(teacher)
    evaluation = await _get_evaluation_in_institution(db, teacher, evaluation_id)
    await get_group_with_access(db, teacher, evaluation.group_id)

    answer = await get_answer_by_id(db, answer_id)
    if answer is None:
        raise NotFoundError("Respuesta no encontrada")
    eval_exercise = await get_evaluation_exercise(db, answer.evaluation_exercise_id)
    if eval_exercise is None or eval_exercise.evaluation_id != evaluation_id:
        raise NotFoundError("Respuesta no encontrada en esta evaluación")

    answer.manual_score = score
    answer.reviewed_by_id = teacher.id
    answer.reviewed_at = datetime.now(UTC)
    await db.flush()

    attempt = await get_attempt_by_id(db, answer.attempt_id)
    assert attempt is not None
    if attempt.status != AttemptStatus.in_progress:
        eval_exercises = await list_evaluation_exercises(db, evaluation_id)
        answers = {
            a.evaluation_exercise_id: a for a in await list_answers_for_attempt(db, attempt.id)
        }
        attempt.total_score = _weighted_total(eval_exercises, answers)
        await db.flush()

    return answer


async def _enabled_topic_ids_for_group(db: AsyncSession, group_id: uuid.UUID) -> set[uuid.UUID]:
    states = await list_topic_group_states_for_group(db, group_id)
    return {s.topic_id for s in states if s.state == TopicGroupStateValue.enabled}


async def list_practice_exercises(
    db: AsyncSession, student: User, group_id: uuid.UUID
) -> list[Exercise]:
    membership = await get_membership(db, group_id, student.id)
    if membership is None:
        raise PermissionDeniedError("No perteneces a este grupo")

    enabled_topic_ids = await _enabled_topic_ids_for_group(db, group_id)
    if not enabled_topic_ids:
        return []

    seen: set[uuid.UUID] = set()
    exercises: list[Exercise] = []
    for topic_id in enabled_topic_ids:
        for exercise in await list_exercises(db, student.institution_id, topic_id=topic_id):
            if exercise.id in seen or exercise.status != ExerciseStatus.published:
                continue
            seen.add(exercise.id)
            exercises.append(exercise)
    return exercises


async def submit_practice(
    db: AsyncSession,
    student: User,
    exercise_id: uuid.UUID,
    group_id: uuid.UUID,
    answer: dict[str, Any],
) -> PracticeSubmission:
    membership = await get_membership(db, group_id, student.id)
    if membership is None:
        raise PermissionDeniedError("No perteneces a este grupo")

    exercise = await get_exercise(db, exercise_id)
    if exercise is None or exercise.institution_id != student.institution_id:
        raise NotFoundError("Ejercicio no encontrado")
    if exercise.status != ExerciseStatus.published:
        raise NotFoundError("Ejercicio no encontrado")

    topic_ids = await list_topic_ids_for_exercise(db, exercise_id)
    enabled_topic_ids = await _enabled_topic_ids_for_group(db, group_id)
    if not any(tid in enabled_topic_ids for tid in topic_ids):
        raise PermissionDeniedError("Este ejercicio no está habilitado para tu grupo")

    result = await _grade(exercise, answer)
    submission = PracticeSubmission(
        institution_id=student.institution_id,
        student_id=student.id,
        exercise_id=exercise_id,
        group_id=group_id,
        answer=answer,
        score=result.score,
        correct=result.correct,
        needs_manual_review=result.needs_manual_review,
    )
    db.add(submission)
    await db.flush()
    return submission


def sanitize_exercise_content(exercise: Exercise) -> dict[str, Any]:
    return strip_answer_key(exercise.type, exercise.content)
