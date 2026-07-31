"""Servicio de progreso (RF-29, RF-15, RF-17). Puntos e insignias se derivan
de la práctica libre (RF-09) — intentos ilimitados, retroalimentación
inmediata — que es la señal más fiel de dominio continuo; las evaluaciones
(RF-20/21) ya tienen su propio ranking (Fase 3) y aportan puntos, pero no
"dominio por tema/lenguaje"."""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import PermissionDeniedError
from logica.modules.assignments.service import list_my_assignments
from logica.modules.exercises.models import Exercise
from logica.modules.groups.service import get_group_with_access
from logica.modules.progress import repository
from logica.modules.progress.models import AcademicPeriod, Badge, BadgeCriteria, StudentBadge
from logica.modules.progress.schemas import (
    BadgeOut,
    DailyActivityOut,
    LaggingStudentOut,
    LanguageMasteryOut,
    StudentActivityOut,
    StudentProgressOut,
    TimelineEventOut,
    TodaySummaryOut,
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


def _streaks(active_days: set[date], today: date) -> tuple[int, int]:
    """(racha actual, racha máxima) en días consecutivos con actividad.

    La racha actual cuenta hacia atrás desde hoy y **tolera que hoy esté
    vacío**: a las 9 a.m. todavía no practicaste, y decirle a alguien que
    perdió su racha de 20 días por eso lo castiga por la hora en que abre la
    página. Se rompe solo cuando ayer tampoco hubo actividad.
    """
    if not active_days:
        return 0, 0

    current = 0
    cursor = today if today in active_days else today - timedelta(days=1)
    while cursor in active_days:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    previous: date | None = None
    for day in sorted(active_days):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day

    return current, longest


async def get_student_activity(
    db: AsyncSession, student: User, *, days: int, tz_name: str
) -> StudentActivityOut:
    """Serie diaria + rachas + conexiones: el "perfil" del estudiante.

    Todo se deriva de datos que ya existen (`practice_submissions.created_at` y
    `audit_logs`), sin tablas nuevas.
    """
    now = datetime.now(UTC)
    rows = await repository.daily_practice_activity(
        db, student.id, since=now - timedelta(days=days), tz_name=tz_name
    )

    try:
        today = now.astimezone(ZoneInfo(tz_name)).date()
    except ZoneInfoNotFoundError:
        # Zona desconocida (cliente con un tz raro o datos de zona ausentes en
        # la imagen): la serie ya viene agrupada por Postgres, así que degradar
        # a UTC solo desplaza el "hoy" de las rachas, no rompe la respuesta.
        today = now.date()

    active_days = {day for day, submissions, _ in rows if submissions > 0}
    current_streak, longest_streak = _streaks(active_days, today)

    return StudentActivityOut(
        days=[
            DailyActivityOut(date=day, submissions=submissions, correct=correct)
            for day, submissions, correct in rows
        ],
        current_streak=current_streak,
        longest_streak=longest_streak,
        active_days=len(active_days),
        total_submissions=sum(submissions for _, submissions, _ in rows),
        logins=await repository.count_logins(db, student.id),
    )


async def get_today_summary(db: AsyncSession, student: User, *, tz_name: str) -> TodaySummaryOut:
    """ "Mi progreso hoy": reusa `get_student_activity` (misma racha, mismo
    derivado de `practice_submissions`) en vez de una consulta nueva de un
    solo día — la racha necesita el historial completo para calcularse, no
    solo la ventana de hoy."""
    activity = await get_student_activity(db, student, days=365, tz_name=tz_name)

    now = datetime.now(UTC)
    try:
        today = now.astimezone(ZoneInfo(tz_name)).date()
    except ZoneInfoNotFoundError:
        today = now.date()

    today_row = next((d for d in activity.days if d.date == today), None)
    submissions = today_row.submissions if today_row else 0
    correct = today_row.correct if today_row else 0

    badge_rows = [
        b
        for b in await repository.list_student_badges(db, student.id)
        if b.earned_at.astimezone(UTC).date() == today
    ]
    badges_by_id = {b.id: b for b in await repository.list_badges(db, student.institution_id)}
    badges_earned_today = _build_badge_outs(badge_rows, badges_by_id)

    assignments = await list_my_assignments(db, student)
    due_today = sum(
        1 for a in assignments if not a.done and a.due_at is not None and a.due_at.date() == today
    )
    due_tomorrow = sum(
        1
        for a in assignments
        if not a.done and a.due_at is not None and a.due_at.date() == today + timedelta(days=1)
    )

    return TodaySummaryOut(
        submissions=submissions,
        correct=correct,
        current_streak=activity.current_streak,
        badges_earned_today=badges_earned_today,
        due_today=due_today,
        due_tomorrow=due_tomorrow,
    )


def _build_badge_outs(
    badge_rows: list[StudentBadge], badges_by_id: dict[uuid.UUID, Badge]
) -> list[BadgeOut]:
    return [
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


async def get_student_progress(db: AsyncSession, student: User) -> StudentProgressOut:
    practice_total, practice_correct = await repository.count_correct_practice(db, student.id)
    evaluation_points = await repository.sum_submitted_evaluation_scores(db, student.id)
    # RF-29: gamification points, not a grading metric — 1 per correct
    # practice submission, plus 10x the accumulated evaluation score (formal
    # assessments count for more than free practice).
    points = practice_correct + round(evaluation_points * 10)

    badge_rows = await repository.list_student_badges(db, student.id)
    badges_by_id = {b.id: b for b in await repository.list_badges(db, student.institution_id)}
    badges = _build_badge_outs(badge_rows, badges_by_id)

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


async def get_student_timeline(
    db: AsyncSession, student: User, *, limit: int
) -> list[TimelineEventOut]:
    """Feed cronológico (ítem 6): fusiona 3 fuentes ya existentes en Python en
    vez de un `UNION` SQL — cada fuente ya trae como mucho `limit` filas, así
    que ordenar la unión en memoria es más simple que un UNION tipado entre
    tres tablas con columnas distintas."""
    submissions, badges, attempts = (
        await repository.recent_practice_submissions(db, student.id, limit),
        await repository.recent_student_badges(db, student.id, limit),
        await repository.recent_evaluation_attempts(db, student.id, limit),
    )

    events = [
        TimelineEventOut(
            kind="practice",
            title=title,
            detail="Correcto" if submission.correct else "Incorrecto",
            occurred_at=submission.created_at,
        )
        for submission, title in submissions
    ]
    events += [
        TimelineEventOut(
            kind="badge",
            title=name,
            detail="Insignia ganada",
            occurred_at=badge.earned_at,
        )
        for badge, name in badges
    ]
    events += [
        TimelineEventOut(
            kind="evaluation",
            title=title,
            detail=(
                f"Puntaje: {attempt.total_score:.1f}"
                if attempt.total_score is not None
                else "Entregada"
            ),
            occurred_at=attempt.submitted_at,
        )
        for attempt, title in attempts
        if attempt.submitted_at is not None
    ]

    events.sort(key=lambda e: e.occurred_at, reverse=True)
    return events[:limit]


async def lagging_reason_for_student(
    db: AsyncSession,
    group_id: uuid.UUID,
    student_id: uuid.UUID,
    *,
    topic_id: uuid.UUID | None = None,
) -> tuple[str | None, float | None, int | None]:
    """(reason, accuracy, days_since_last_activity) — sin chequeo de permisos,
    pensado para reusarse desde un job en background (reportes) además del
    endpoint de docente. `reason` es `None` si el estudiante no está rezagado."""
    total, correct, last_at = await repository.practice_accuracy_and_last_activity_in_group(
        db, group_id, student_id, topic_id=topic_id
    )
    accuracy = _accuracy(total, correct)
    now = datetime.now(UTC)
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

    return reason, accuracy, days_since


async def get_lagging_students(
    db: AsyncSession, teacher: User, group_id: uuid.UUID, *, topic_id: uuid.UUID | None = None
) -> list[LaggingStudentOut]:
    """RF-15: a rule-based check (accuracy or inactivity), not a judgment
    call left to an LLM — a teacher deserves a deterministic, explainable
    reason for why a student is flagged. Pairs naturally with the Learning
    Analytics agent's `summarize_group` (Fase 6) for a narrative summary of
    the same underlying data. `topic_id` narrows the check to one topic's
    practice — a student can be fine overall but stuck on a single topic."""
    _, is_teacher_view = await get_group_with_access(db, teacher, group_id)
    if not is_teacher_view:
        raise PermissionDeniedError("Solo un docente o administrador puede ver esta vista")

    lagging: list[LaggingStudentOut] = []
    for student_id in await repository.group_member_ids(db, group_id):
        reason, accuracy, days_since = await lagging_reason_for_student(
            db, group_id, student_id, topic_id=topic_id
        )
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
    "lagging_reason_for_student",
    "list_academic_periods",
]
