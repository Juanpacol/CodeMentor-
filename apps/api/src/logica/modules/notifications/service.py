"""Notificaciones inteligentes (ítem 5): reglas deterministas sobre datos que
ya existen (tareas, insignias, racha) — mismo precedente de "regla explicable,
no juicio de un LLM" que `progress.service.get_lagging_students`. Se generan
de forma perezosa en cada `GET /notifications`, sin cola/daemon aparte."""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.errors import NotFoundError
from logica.modules.assignments.service import list_my_assignments
from logica.modules.notifications import repository
from logica.modules.notifications.models import Notification, NotificationKind
from logica.modules.progress import repository as progress_repository
from logica.modules.progress.service import get_student_activity
from logica.modules.users.models import User

# No regenerar la misma notificación más de una vez en esta ventana — evita
# "tu tarea vence mañana" repetida en cada carga de la página.
_DEDUPE_WINDOW = timedelta(hours=20)
_STREAK_AT_RISK_MIN = 3


def _today_in_tz(now: datetime, tz_name: str) -> date:
    try:
        return now.astimezone(ZoneInfo(tz_name)).date()
    except ZoneInfoNotFoundError:
        return now.date()


async def _sync_assignment_due(
    db: AsyncSession, student: User, *, today: date, since: datetime
) -> None:
    for assignment in await list_my_assignments(db, student):
        if assignment.done or assignment.due_at is None:
            continue
        days_left = (assignment.due_at.date() - today).days
        if days_left not in (0, 1):
            continue
        existing = await repository.find_recent(
            db,
            student.id,
            kind=NotificationKind.assignment_due,
            related_id=assignment.id,
            since=since,
        )
        if existing is not None:
            continue
        when = "hoy" if days_left == 0 else "mañana"
        await repository.create(
            db,
            institution_id=student.institution_id,
            user_id=student.id,
            kind=NotificationKind.assignment_due,
            title=f"'{assignment.title}' vence {when}",
            body=f"Tu tarea en {assignment.group_name} vence {when}.",
            related_id=assignment.id,
        )


async def _sync_badges_earned(
    db: AsyncSession, student: User, *, now: datetime, since: datetime
) -> None:
    badge_rows = await progress_repository.list_student_badges(db, student.id)
    badges_by_id = {
        b.id: b for b in await progress_repository.list_badges(db, student.institution_id)
    }
    for row in badge_rows:
        if row.earned_at < now - timedelta(hours=24):
            continue
        badge = badges_by_id.get(row.badge_id)
        if badge is None:
            continue
        existing = await repository.find_recent(
            db, student.id, kind=NotificationKind.badge_earned, related_id=row.id, since=since
        )
        if existing is not None:
            continue
        await repository.create(
            db,
            institution_id=student.institution_id,
            user_id=student.id,
            kind=NotificationKind.badge_earned,
            title=f"Ganaste: {badge.name}",
            body=badge.description,
            related_id=row.id,
        )


async def _sync_streak_at_risk(
    db: AsyncSession, student: User, *, tz_name: str, today: date, since: datetime
) -> None:
    activity = await get_student_activity(db, student, days=365, tz_name=tz_name)
    if activity.current_streak < _STREAK_AT_RISK_MIN:
        return
    today_has_activity = any(d.date == today and d.submissions > 0 for d in activity.days)
    if today_has_activity:
        return
    existing = await repository.find_recent(
        db, student.id, kind=NotificationKind.streak_at_risk, related_id=None, since=since
    )
    if existing is not None:
        return
    await repository.create(
        db,
        institution_id=student.institution_id,
        user_id=student.id,
        kind=NotificationKind.streak_at_risk,
        title="Tu racha está en riesgo",
        body=f"Llevas {activity.current_streak} días seguidos practicando — no la pierdas hoy.",
        related_id=None,
    )


async def sync_notifications_for_student(db: AsyncSession, student: User, *, tz_name: str) -> None:
    now = datetime.now(UTC)
    today = _today_in_tz(now, tz_name)
    since = now - _DEDUPE_WINDOW
    await _sync_assignment_due(db, student, today=today, since=since)
    await _sync_badges_earned(db, student, now=now, since=since)
    await _sync_streak_at_risk(db, student, tz_name=tz_name, today=today, since=since)
    await db.flush()


async def list_notifications_for_student(
    db: AsyncSession, student: User, *, tz_name: str
) -> tuple[list[Notification], int]:
    await sync_notifications_for_student(db, student, tz_name=tz_name)
    notifications = await repository.list_for_user(db, student.id)
    unread_count = await repository.count_unread(db, student.id)
    return notifications, unread_count


async def mark_read(db: AsyncSession, student: User, notification_id: uuid.UUID) -> Notification:
    notification = await repository.get_for_user(db, student.id, notification_id)
    if notification is None:
        raise NotFoundError("Notificación no encontrada")
    notification.read_at = datetime.now(UTC)
    await db.flush()
    return notification


async def mark_all_read(db: AsyncSession, student: User) -> None:
    await repository.mark_all_read(db, student.id, now=datetime.now(UTC))
    await db.flush()
