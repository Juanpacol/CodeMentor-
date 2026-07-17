import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.evaluations.models import (
    AttemptStatus,
    Evaluation,
    EvaluationAttempt,
    PracticeSubmission,
)
from logica.modules.groups.models import GroupMembership
from logica.modules.progress.models import StudentBadge
from logica.modules.reports.models import ReportFormat, ReportJob, ReportStatus
from logica.modules.users.models import User


@dataclass(frozen=True)
class StudentReportRow:
    full_name: str
    email: str
    practice_total: int
    practice_correct: int
    evaluations_submitted: int
    avg_evaluation_score: float | None
    badges_count: int


async def create_report_job(
    db: AsyncSession,
    institution_id: uuid.UUID,
    requested_by_id: uuid.UUID,
    group_id: uuid.UUID,
    format: ReportFormat,
    period_id: uuid.UUID | None,
) -> ReportJob:
    job = ReportJob(
        institution_id=institution_id,
        requested_by_id=requested_by_id,
        group_id=group_id,
        format=format,
        period_id=period_id,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def get_report_job(db: AsyncSession, report_job_id: uuid.UUID) -> ReportJob | None:
    return await db.get(ReportJob, report_job_id)


async def mark_processing(db: AsyncSession, job: ReportJob) -> None:
    job.status = ReportStatus.processing
    await db.flush()


async def mark_done(db: AsyncSession, job: ReportJob, file_path: str) -> None:
    job.status = ReportStatus.done
    job.file_path = file_path
    job.completed_at = datetime.now(UTC)
    await db.flush()


async def mark_failed(db: AsyncSession, job: ReportJob, error_message: str) -> None:
    job.status = ReportStatus.failed
    job.error_message = error_message
    await db.flush()


async def student_report_rows(
    db: AsyncSession,
    group_id: uuid.UUID,
    *,
    period_start: date | None,
    period_end: date | None,
) -> list[StudentReportRow]:
    """One row per enrolled student (RF-16), each computed with its own small
    queries rather than one large join — the group's roster is small enough
    (a school class) that this stays fast, and it keeps each aggregate
    independently readable/testable."""
    members_stmt = (
        select(User)
        .join(GroupMembership, GroupMembership.student_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(User.full_name)
    )
    students = list((await db.execute(members_stmt)).scalars().all())

    rows: list[StudentReportRow] = []
    for student in students:
        practice_stmt = select(
            func.count(PracticeSubmission.id),
            func.count(PracticeSubmission.id).filter(PracticeSubmission.correct.is_(True)),
        ).where(
            PracticeSubmission.group_id == group_id, PracticeSubmission.student_id == student.id
        )
        if period_start is not None:
            practice_stmt = practice_stmt.where(PracticeSubmission.created_at >= period_start)
        if period_end is not None:
            practice_stmt = practice_stmt.where(PracticeSubmission.created_at <= period_end)
        practice_total, practice_correct = (await db.execute(practice_stmt)).one()

        eval_stmt = (
            select(func.count(EvaluationAttempt.id), func.avg(EvaluationAttempt.total_score))
            .select_from(EvaluationAttempt)
            .join(Evaluation, Evaluation.id == EvaluationAttempt.evaluation_id)
            .where(
                Evaluation.group_id == group_id,
                EvaluationAttempt.student_id == student.id,
                EvaluationAttempt.status == AttemptStatus.submitted,
            )
        )
        if period_start is not None:
            eval_stmt = eval_stmt.where(EvaluationAttempt.submitted_at >= period_start)
        if period_end is not None:
            eval_stmt = eval_stmt.where(EvaluationAttempt.submitted_at <= period_end)
        evaluations_submitted, avg_score = (await db.execute(eval_stmt)).one()

        badges_stmt = select(func.count(StudentBadge.id)).where(
            StudentBadge.student_id == student.id
        )
        badges_count = (await db.execute(badges_stmt)).scalar_one()

        rows.append(
            StudentReportRow(
                full_name=student.full_name,
                email=student.email,
                practice_total=practice_total,
                practice_correct=int(practice_correct or 0),
                evaluations_submitted=evaluations_submitted,
                avg_evaluation_score=float(avg_score) if avg_score is not None else None,
                badges_count=badges_count,
            )
        )
    return rows
