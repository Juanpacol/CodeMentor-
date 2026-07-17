import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from logica.modules.content.models import Language, Topic
from logica.modules.evaluations.models import AttemptStatus, EvaluationAttempt, PracticeSubmission
from logica.modules.exercises.models import Exercise, TopicExercise
from logica.modules.groups.models import GroupMembership
from logica.modules.progress.models import AcademicPeriod, Badge, BadgeCriteria, StudentBadge

_CORRECT_AS_INT = cast(PracticeSubmission.correct, Integer)


async def get_badge_by_slug(db: AsyncSession, institution_id: uuid.UUID, slug: str) -> Badge | None:
    stmt = select(Badge).where(Badge.institution_id == institution_id, Badge.slug == slug)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_badges(db: AsyncSession, institution_id: uuid.UUID) -> list[Badge]:
    stmt = select(Badge).where(Badge.institution_id == institution_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _scope_filter(column: Any, value: uuid.UUID | None) -> ColumnElement[bool]:
    result: ColumnElement[bool] = column.is_(None) if value is None else column == value
    return result


async def get_student_badge(
    db: AsyncSession,
    student_id: uuid.UUID,
    badge_id: uuid.UUID,
    *,
    language_id: uuid.UUID | None,
    topic_id: uuid.UUID | None,
) -> StudentBadge | None:
    stmt = select(StudentBadge).where(
        StudentBadge.student_id == student_id,
        StudentBadge.badge_id == badge_id,
        _scope_filter(StudentBadge.language_id, language_id),
        _scope_filter(StudentBadge.topic_id, topic_id),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_student_badges(db: AsyncSession, student_id: uuid.UUID) -> list[StudentBadge]:
    stmt = select(StudentBadge).where(StudentBadge.student_id == student_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_correct_practice(db: AsyncSession, student_id: uuid.UUID) -> tuple[int, int]:
    """Returns (total, correct) practice submissions for a student, across
    every group/language — the raw ingredients for RF-29 points."""
    total_stmt = select(func.count(PracticeSubmission.id)).where(
        PracticeSubmission.student_id == student_id
    )
    correct_stmt = select(func.count(PracticeSubmission.id)).where(
        PracticeSubmission.student_id == student_id, PracticeSubmission.correct.is_(True)
    )
    total = (await db.execute(total_stmt)).scalar_one()
    correct = (await db.execute(correct_stmt)).scalar_one()
    return total, correct


async def sum_submitted_evaluation_scores(db: AsyncSession, student_id: uuid.UUID) -> float:
    stmt = select(func.coalesce(func.sum(EvaluationAttempt.total_score), 0.0)).where(
        EvaluationAttempt.student_id == student_id,
        EvaluationAttempt.status == AttemptStatus.submitted,
    )
    result = await db.execute(stmt)
    return float(result.scalar_one() or 0.0)


async def mastery_by_topic(
    db: AsyncSession, student_id: uuid.UUID, institution_id: uuid.UUID
) -> list[tuple[Topic, int, int]]:
    """(topic, total_submissions, correct_submissions) for every topic that
    has at least one practice submission from this student. Practice
    (RF-09, unlimited attempts, immediate feedback) is the natural signal for
    "mastery" — evaluations measure a point in time, practice measures the
    ongoing skill."""
    stmt = (
        select(Topic, func.count(PracticeSubmission.id), func.sum(_CORRECT_AS_INT))
        .select_from(Topic)
        .join(TopicExercise, TopicExercise.topic_id == Topic.id)
        .join(PracticeSubmission, PracticeSubmission.exercise_id == TopicExercise.exercise_id)
        .where(PracticeSubmission.student_id == student_id, Topic.institution_id == institution_id)
        .group_by(Topic.id)
    )
    result = await db.execute(stmt)
    return [(topic, total, int(correct or 0)) for topic, total, correct in result.all()]


async def mastery_by_language(
    db: AsyncSession, student_id: uuid.UUID, institution_id: uuid.UUID
) -> list[tuple[Language, int, int]]:
    stmt = (
        select(Language, func.count(PracticeSubmission.id), func.sum(_CORRECT_AS_INT))
        .select_from(Language)
        .join(Exercise, Exercise.language_id == Language.id)
        .join(PracticeSubmission, PracticeSubmission.exercise_id == Exercise.id)
        .where(
            PracticeSubmission.student_id == student_id, Language.institution_id == institution_id
        )
        .group_by(Language.id)
    )
    result = await db.execute(stmt)
    return [(language, total, int(correct or 0)) for language, total, correct in result.all()]


async def topic_accuracy(
    db: AsyncSession, student_id: uuid.UUID, topic_id: uuid.UUID
) -> tuple[int, int]:
    """(total, correct) for one topic — the cheap, single-topic version of
    `mastery_by_topic`, used right after a practice submission to check just
    the topic(s) that submission touched instead of recomputing every topic
    the student has ever practiced."""
    stmt = (
        select(func.count(PracticeSubmission.id), func.sum(_CORRECT_AS_INT))
        .select_from(TopicExercise)
        .join(PracticeSubmission, PracticeSubmission.exercise_id == TopicExercise.exercise_id)
        .where(TopicExercise.topic_id == topic_id, PracticeSubmission.student_id == student_id)
    )
    total, correct = (await db.execute(stmt)).one()
    return total, int(correct or 0)


async def language_accuracy(
    db: AsyncSession, student_id: uuid.UUID, language_id: uuid.UUID
) -> tuple[int, int]:
    stmt = (
        select(func.count(PracticeSubmission.id), func.sum(_CORRECT_AS_INT))
        .select_from(Exercise)
        .join(PracticeSubmission, PracticeSubmission.exercise_id == Exercise.id)
        .where(Exercise.language_id == language_id, PracticeSubmission.student_id == student_id)
    )
    total, correct = (await db.execute(stmt)).one()
    return total, int(correct or 0)


async def recent_practice_correctness(
    db: AsyncSession, student_id: uuid.UUID, limit: int
) -> list[bool]:
    """Most-recent-first `correct` flags, used to compute a trailing streak
    (RF-29 `practice_streak` badge)."""
    stmt = (
        select(PracticeSubmission.correct)
        .where(PracticeSubmission.student_id == student_id)
        .order_by(PracticeSubmission.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def group_member_ids(db: AsyncSession, group_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(GroupMembership.student_id).where(GroupMembership.group_id == group_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def practice_accuracy_and_last_activity_in_group(
    db: AsyncSession, group_id: uuid.UUID, student_id: uuid.UUID
) -> tuple[int, int, datetime | None]:
    """(total, correct, last_submission_at) restricted to one group — used
    for RF-15 lag detection, which is inherently per-group (a student can be
    fine in one group's pace and behind in another)."""
    stmt = select(
        func.count(PracticeSubmission.id),
        func.sum(_CORRECT_AS_INT),
        func.max(PracticeSubmission.created_at),
    ).where(PracticeSubmission.group_id == group_id, PracticeSubmission.student_id == student_id)
    result = await db.execute(stmt)
    total, correct, last_at = result.one()
    return total, int(correct or 0), last_at


async def create_academic_period(
    db: AsyncSession, institution_id: uuid.UUID, name: str, start_date: date, end_date: date
) -> AcademicPeriod:
    period = AcademicPeriod(
        institution_id=institution_id, name=name, start_date=start_date, end_date=end_date
    )
    db.add(period)
    await db.flush()
    await db.refresh(period)
    return period


async def list_academic_periods(
    db: AsyncSession, institution_id: uuid.UUID
) -> list[AcademicPeriod]:
    stmt = (
        select(AcademicPeriod)
        .where(AcademicPeriod.institution_id == institution_id)
        .order_by(AcademicPeriod.start_date.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_academic_period(db: AsyncSession, period_id: uuid.UUID) -> AcademicPeriod | None:
    return await db.get(AcademicPeriod, period_id)


__all__ = [
    "BadgeCriteria",
    "count_correct_practice",
    "create_academic_period",
    "get_academic_period",
    "get_badge_by_slug",
    "get_student_badge",
    "group_member_ids",
    "language_accuracy",
    "list_academic_periods",
    "list_badges",
    "list_student_badges",
    "mastery_by_language",
    "mastery_by_topic",
    "practice_accuracy_and_last_activity_in_group",
    "recent_practice_correctness",
    "sum_submitted_evaluation_scores",
    "topic_accuracy",
]
