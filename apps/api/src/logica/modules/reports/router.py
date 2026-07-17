import uuid
from pathlib import Path

from arq import ArqRedis
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from logica.core.arq_dep import get_arq_pool
from logica.core.errors import ConflictError, NotFoundError
from logica.core.permissions import require_role
from logica.db import get_db
from logica.modules.reports import service
from logica.modules.reports.models import ReportStatus
from logica.modules.reports.schemas import (
    GradebookEvaluationOut,
    GradebookOut,
    GradebookScoreOut,
    GradebookStudentOut,
    ReportJobOut,
    ReportRequest,
)
from logica.modules.users.models import User

router = APIRouter(tags=["reports"])

RequireTeacher = require_role("teacher", "admin")

_CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.post("/groups/{group_id}/reports", response_model=ReportJobOut, status_code=202)
async def request_group_report(
    group_id: uuid.UUID,
    payload: ReportRequest,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> ReportJobOut:
    job = await service.request_group_report(
        db, arq_pool, user, group_id, payload.format, payload.period_id
    )
    await db.commit()
    return ReportJobOut.model_validate(job)


@router.get("/reports/{report_job_id}", response_model=ReportJobOut)
async def get_report_job(
    report_job_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> ReportJobOut:
    job = await service.get_report_job_for_user(db, user, report_job_id)
    return ReportJobOut.model_validate(job)


@router.get("/reports/{report_job_id}/download")
async def download_report(
    report_job_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    job = await service.get_report_job_for_user(db, user, report_job_id)
    if job.status != ReportStatus.done or job.file_path is None:
        raise ConflictError("El reporte todavía no está listo")
    path = Path(job.file_path)
    if not path.exists():  # noqa: ASYNC240 — a stat() call, not the report generation itself
        raise NotFoundError("El archivo del reporte ya no está disponible")
    return FileResponse(
        path,
        media_type=_CONTENT_TYPES[job.format.value],
        filename=f"reporte-{job.group_id}.{job.format.value}",
    )


@router.get("/groups/{group_id}/gradebook", response_model=GradebookOut)
async def get_gradebook(
    group_id: uuid.UUID,
    user: User = Depends(RequireTeacher),
    db: AsyncSession = Depends(get_db),
) -> GradebookOut:
    evaluations, students = await service.get_group_gradebook(db, user, group_id)
    return GradebookOut(
        evaluations=[GradebookEvaluationOut.model_validate(e) for e in evaluations],
        students=[
            GradebookStudentOut(
                student_id=row.student_id,
                full_name=row.full_name,
                scores=[
                    GradebookScoreOut(evaluation_id=s.evaluation_id, total_score=s.total_score)
                    for s in row.scores
                ],
                evaluations_submitted=row.evaluations_submitted,
                avg_evaluation_score=row.avg_evaluation_score,
            )
            for row in students
        ],
    )
