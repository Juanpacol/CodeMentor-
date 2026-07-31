import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logica.modules.evaluations.models import (
    AttemptStatus,
    Evaluation,
    EvaluationAttempt,
    EvaluationExercise,
    PracticeSubmission,
)
from logica.modules.groups.models import GroupMembership
from logica.modules.progress.models import StudentBadge
from logica.modules.reports.models import ReportFormat, ReportJob, ReportStatus
from logica.modules.users.models import User


@dataclass(frozen=True)
class StudentReportRow:
    student_id: uuid.UUID
    full_name: str
    email: str
    practice_total: int
    practice_correct: int
    evaluations_submitted: int
    avg_evaluation_score: float | None
    badges_count: int


@dataclass(frozen=True)
class GradebookScore:
    evaluation_id: uuid.UUID
    total_score: float


@dataclass(frozen=True)
class GradebookStudentRow:
    student_id: uuid.UUID
    full_name: str
    scores: list[GradebookScore]
    evaluations_submitted: int
    avg_evaluation_score: float | None
    # Suma de (nota/máximo) × peso, solo sobre las evaluaciones con
    # `weight_percent` definido y con intento presentado — None si ninguna
    # evaluación del grupo tiene peso asignado o el estudiante no ha
    # presentado ninguna de ellas.
    weighted_average: float | None


async def create_report_job(
    db: AsyncSession,
    institution_id: uuid.UUID,
    requested_by_id: uuid.UUID,
    group_id: uuid.UUID,
    format: ReportFormat,
) -> ReportJob:
    job = ReportJob(
        institution_id=institution_id,
        requested_by_id=requested_by_id,
        group_id=group_id,
        format=format,
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
        evaluations_submitted, avg_score = (await db.execute(eval_stmt)).one()

        badges_stmt = select(func.count(StudentBadge.id)).where(
            StudentBadge.student_id == student.id
        )
        badges_count = (await db.execute(badges_stmt)).scalar_one()

        rows.append(
            StudentReportRow(
                student_id=student.id,
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


async def gradebook_rows(
    db: AsyncSession, group_id: uuid.UUID
) -> tuple[list[Evaluation], list[GradebookStudentRow]]:
    """Vista en vivo de calificaciones (a diferencia de `student_report_rows`,
    usada por el export async xlsx/pdf): misma definición de
    `avg_evaluation_score` — promedio de `total_score` sobre intentos
    presentados — para que ambas vistas coincidan, pero aquí se conserva el
    detalle por evaluación en vez de solo el promedio."""
    evaluations_stmt = (
        select(Evaluation).where(Evaluation.group_id == group_id).order_by(Evaluation.created_at)
    )
    evaluations = list((await db.execute(evaluations_stmt)).scalars().all())

    members_stmt = (
        select(User)
        .join(GroupMembership, GroupMembership.student_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(User.full_name)
    )
    students = list((await db.execute(members_stmt)).scalars().all())

    attempts_stmt = (
        select(
            EvaluationAttempt.student_id,
            EvaluationAttempt.evaluation_id,
            EvaluationAttempt.total_score,
        )
        .join(Evaluation, Evaluation.id == EvaluationAttempt.evaluation_id)
        .where(
            Evaluation.group_id == group_id,
            EvaluationAttempt.status == AttemptStatus.submitted,
        )
    )
    attempts = (await db.execute(attempts_stmt)).all()

    scores_by_student: dict[uuid.UUID, list[GradebookScore]] = {}
    for student_id, evaluation_id, total_score in attempts:
        scores_by_student.setdefault(student_id, []).append(
            GradebookScore(evaluation_id=evaluation_id, total_score=total_score)
        )

    # Máximo posible por evaluación (suma de `points` de sus ejercicios): hace
    # falta para normalizar `total_score` (una suma en escala arbitraria, no
    # 0-100) antes de aplicarle el peso de la evaluación.
    max_score_stmt = (
        select(EvaluationExercise.evaluation_id, func.sum(EvaluationExercise.points))
        .join(Evaluation, Evaluation.id == EvaluationExercise.evaluation_id)
        .where(Evaluation.group_id == group_id)
        .group_by(EvaluationExercise.evaluation_id)
    )
    max_score_by_evaluation: dict[uuid.UUID, float] = dict(
        (await db.execute(max_score_stmt)).tuples().all()
    )
    weight_by_evaluation = {e.id: e.weight_percent for e in evaluations}

    def _weighted_average(scores: list[GradebookScore]) -> float | None:
        contributions = []
        for s in scores:
            weight = weight_by_evaluation.get(s.evaluation_id)
            max_score = max_score_by_evaluation.get(s.evaluation_id)
            if weight is None or not max_score:
                continue
            contributions.append((s.total_score / max_score) * weight)
        return sum(contributions) if contributions else None

    rows: list[GradebookStudentRow] = []
    for student in students:
        scores = scores_by_student.get(student.id, [])
        avg_score = sum(s.total_score for s in scores) / len(scores) if scores else None
        rows.append(
            GradebookStudentRow(
                student_id=student.id,
                full_name=student.full_name,
                scores=scores,
                evaluations_submitted=len(scores),
                avg_evaluation_score=avg_score,
                weighted_average=_weighted_average(scores),
            )
        )
    return evaluations, rows
