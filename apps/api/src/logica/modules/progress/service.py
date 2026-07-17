"""Servicio de progreso (RF-29, RF-15, RF-17). Puntos e insignias se derivan
de la práctica libre (RF-09) — intentos ilimitados, retroalimentación
inmediata — que es la señal más fiel de dominio continuo; las evaluaciones
(RF-20/21) ya tienen su propio ranking (Fase 3) y aportan puntos, pero no
"dominio por tema/lenguaje"."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import PermissionDeniedError
from logica.modules.exercises.models import Exercise
from logica.modules.groups.service import get_group_with_access
from logica.modules.progress import repository
from logica.modules.progress.models import AcademicPeriod, Badge, BadgeCriteria, StudentBadge
from logica.modules.progress.schemas import (
    BadgeOut,
    LaggingStudentOut,
    LanguageMasteryOut,
    StudentProgressOut,
    TopicMasteryOut,
)
from logica.modules.users.models import Role, User
from logica.modules.users.repository import get_user_by_id

# RF-29: umbrales elegidos para que una insignia signifique algo (no se gana
# con 1-2 aciertos de suerte) sin ser inalcanzable en una sola clase.
_MASTERY_MIN_SUBMISSIONS = 5
_MASTERY_ACCURACY_THRESHOLD = 0.8
_STREAK_THRESHOLD = 5

# RF-15: sin actividad de práctica en este número de días, o precisión por
# debajo de este umbral con al menos unos pocos envíos, se marca como rezago.
_LAG_INACTIVITY_DAYS = 7
_LAG_ACCURACY_THRESHOLD = 0.5
_LAG_MIN_SUBMISSIONS = 3

_DEFAULT_BADGES: list[tuple[str, str, str, BadgeCriteria, float]] = [
    (
        "dominando-tema",
        "Dominando el tema",
        f"Al menos {int(_MASTERY_ACCURACY_THRESHOLD * 100)}% de aciertos en un tema "
        f"(mínimo {_MASTERY_MIN_SUBMISSIONS} ejercicios de práctica).",
        BadgeCriteria.topic_mastery,
        _MASTERY_ACCURACY_THRESHOLD,
    ),
    (
        "dominando-lenguaje",
        "Dominando el lenguaje",
        f"Al menos {int(_MASTERY_ACCURACY_THRESHOLD * 100)}% de aciertos en un lenguaje "
        f"(mínimo {_MASTERY_MIN_SUBMISSIONS} ejercicios de práctica).",
        BadgeCriteria.language_mastery,
        _MASTERY_ACCURACY_THRESHOLD,
    ),
    (
        "racha-de-aciertos",
        "Racha de aciertos",
        f"{_STREAK_THRESHOLD} ejercicios de práctica correctos seguidos.",
        BadgeCriteria.practice_streak,
        float(_STREAK_THRESHOLD),
    ),
]


async def ensure_default_badges(db: AsyncSession, institution_id: uuid.UUID) -> dict[str, Badge]:
    """Perezoso en vez de una migración de datos: la primera vez que se
    evalúan insignias para una institución, se crea su catálogo si no
    existe. Idempotente — no duplica si ya existen."""
    existing = {b.slug: b for b in await repository.list_badges(db, institution_id)}
    for slug, name, description, criteria, threshold in _DEFAULT_BADGES:
        if slug in existing:
            continue
        badge = Badge(
            institution_id=institution_id,
            slug=slug,
            name=name,
            description=description,
            criteria=criteria,
            threshold=threshold,
        )
        db.add(badge)
        existing[slug] = badge
    await db.flush()
    return existing


async def _award_if_new(
    db: AsyncSession,
    student: User,
    badge: Badge,
    *,
    language_id: uuid.UUID | None,
    topic_id: uuid.UUID | None,
) -> StudentBadge | None:
    already = await repository.get_student_badge(
        db, student.id, badge.id, language_id=language_id, topic_id=topic_id
    )
    if already is not None:
        return None
    earned = StudentBadge(
        institution_id=student.institution_id,
        student_id=student.id,
        badge_id=badge.id,
        language_id=language_id,
        topic_id=topic_id,
        earned_at=datetime.now(UTC),
    )
    db.add(earned)
    await db.flush()
    return earned


def _accuracy(total: int, correct: int) -> float | None:
    return round(correct / total, 2) if total else None


async def evaluate_and_award_badges(
    db: AsyncSession, student: User, *, exercise: Exercise, topic_ids: list[uuid.UUID]
) -> list[StudentBadge]:
    """Called right after a practice submission is recorded (RF-09) — checks
    only the topic(s)/language that submission touched plus the trailing
    streak, not the student's entire history, so this stays cheap enough to
    run inline on every submission."""
    badges = await ensure_default_badges(db, student.institution_id)
    awarded: list[StudentBadge] = []

    topic_badge = badges.get("dominando-tema")
    if topic_badge is not None:
        for topic_id in topic_ids:
            total, correct = await repository.topic_accuracy(db, student.id, topic_id)
            accuracy = _accuracy(total, correct)
            if (
                total >= _MASTERY_MIN_SUBMISSIONS
                and accuracy is not None
                and accuracy >= topic_badge.threshold
            ):
                earned = await _award_if_new(
                    db, student, topic_badge, language_id=None, topic_id=topic_id
                )
                if earned:
                    awarded.append(earned)

    language_badge = badges.get("dominando-lenguaje")
    if language_badge is not None:
        total, correct = await repository.language_accuracy(db, student.id, exercise.language_id)
        accuracy = _accuracy(total, correct)
        if (
            total >= _MASTERY_MIN_SUBMISSIONS
            and accuracy is not None
            and accuracy >= language_badge.threshold
        ):
            earned = await _award_if_new(
                db, student, language_badge, language_id=exercise.language_id, topic_id=None
            )
            if earned:
                awarded.append(earned)

    streak_badge = badges.get("racha-de-aciertos")
    if streak_badge is not None:
        recent = await repository.recent_practice_correctness(
            db, student.id, int(streak_badge.threshold)
        )
        if len(recent) >= streak_badge.threshold and all(recent[: int(streak_badge.threshold)]):
            earned = await _award_if_new(db, student, streak_badge, language_id=None, topic_id=None)
            if earned:
                awarded.append(earned)

    return awarded


async def get_student_progress(db: AsyncSession, student: User) -> StudentProgressOut:
    practice_total, practice_correct = await repository.count_correct_practice(db, student.id)
    evaluation_points = await repository.sum_submitted_evaluation_scores(db, student.id)
    # RF-29: gamification points, not a grading metric — 1 per correct
    # practice submission, plus 10x the accumulated evaluation score (formal
    # assessments count for more than free practice).
    points = practice_correct + round(evaluation_points * 10)

    badge_rows = await repository.list_student_badges(db, student.id)
    badges_by_id = {b.id: b for b in await repository.list_badges(db, student.institution_id)}
    badges = [
        BadgeOut(
            id=row.badge_id,
            slug=badges_by_id[row.badge_id].slug,
            name=badges_by_id[row.badge_id].name,
            description=badges_by_id[row.badge_id].description,
            criteria=badges_by_id[row.badge_id].criteria,
            language_id=row.language_id,
            topic_id=row.topic_id,
            earned_at=row.earned_at,
        )
        for row in badge_rows
        if row.badge_id in badges_by_id
    ]

    topic_mastery = [
        TopicMasteryOut(
            topic_id=topic.id,
            topic_name=topic.name,
            submissions=total,
            accuracy=_accuracy(total, correct),
        )
        for topic, total, correct in await repository.mastery_by_topic(
            db, student.id, student.institution_id
        )
    ]
    language_mastery = [
        LanguageMasteryOut(
            language_id=language.id,
            language_name=language.name,
            submissions=total,
            accuracy=_accuracy(total, correct),
        )
        for language, total, correct in await repository.mastery_by_language(
            db, student.id, student.institution_id
        )
    ]

    return StudentProgressOut(
        student_id=student.id,
        points=points,
        badges=badges,
        mastery_by_topic=topic_mastery,
        mastery_by_language=language_mastery,
    )


async def get_lagging_students(
    db: AsyncSession, teacher: User, group_id: uuid.UUID
) -> list[LaggingStudentOut]:
    """RF-15: a rule-based check (accuracy or inactivity), not a judgment
    call left to an LLM — a teacher deserves a deterministic, explainable
    reason for why a student is flagged. Pairs naturally with the Learning
    Analytics agent's `summarize_group` (Fase 6) for a narrative summary of
    the same underlying data."""
    _, is_teacher_view = await get_group_with_access(db, teacher, group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("Solo un docente o administrador puede ver esta vista")

    lagging: list[LaggingStudentOut] = []
    now = datetime.now(UTC)
    for student_id in await repository.group_member_ids(db, group_id):
        total, correct, last_at = await repository.practice_accuracy_and_last_activity_in_group(
            db, group_id, student_id
        )
        accuracy = _accuracy(total, correct)
        days_since = None
        if last_at is not None:
            last_at_aware = last_at if last_at.tzinfo else last_at.replace(tzinfo=UTC)
            days_since = (now - last_at_aware).days

        reason = None
        if last_at is None or (days_since is not None and days_since >= _LAG_INACTIVITY_DAYS):
            reason = f"Sin práctica en los últimos {_LAG_INACTIVITY_DAYS} días o más"
        elif (
            total >= _LAG_MIN_SUBMISSIONS
            and accuracy is not None
            and (accuracy < _LAG_ACCURACY_THRESHOLD)
        ):
            reason = f"Precisión de práctica por debajo de {int(_LAG_ACCURACY_THRESHOLD * 100)}%"

        if reason is None:
            continue

        student = await get_user_by_id(db, student_id)
        if student is None:
            continue
        lagging.append(
            LaggingStudentOut(
                student_id=student_id,
                full_name=student.full_name,
                accuracy=accuracy,
                days_since_last_activity=days_since,
                reason=reason,
            )
        )
    return lagging


def _ensure_teacher(user: User) -> None:
    if user.role not in (Role.teacher, Role.admin):
        raise PermissionDeniedError(
            "Solo un docente o administrador puede administrar periodos académicos"
        )


async def create_academic_period(
    db: AsyncSession, teacher: User, name: str, start_date: date, end_date: date
) -> AcademicPeriod:
    _ensure_teacher(teacher)
    return await repository.create_academic_period(
        db, teacher.institution_id, name, start_date, end_date
    )


async def list_academic_periods(db: AsyncSession, user: User) -> list[AcademicPeriod]:
    return await repository.list_academic_periods(db, user.institution_id)


__all__ = [
    "create_academic_period",
    "ensure_default_badges",
    "evaluate_and_award_badges",
    "get_lagging_students",
    "get_student_progress",
    "list_academic_periods",
]
