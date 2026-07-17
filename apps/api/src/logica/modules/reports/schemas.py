import uuid
from datetime import datetime

from pydantic import BaseModel

from logica.modules.evaluations.models import EvaluationMode
from logica.modules.reports.models import ReportFormat, ReportStatus


class ReportRequest(BaseModel):
    format: ReportFormat
    period_id: uuid.UUID | None = None


class ReportJobOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    format: ReportFormat
    status: ReportStatus
    error_message: str | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class GradebookEvaluationOut(BaseModel):
    id: uuid.UUID
    title: str
    mode: EvaluationMode
    is_ranked: bool

    model_config = {"from_attributes": True}


class GradebookScoreOut(BaseModel):
    evaluation_id: uuid.UUID
    total_score: float


class GradebookStudentOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    scores: list[GradebookScoreOut]
    evaluations_submitted: int
    avg_evaluation_score: float | None


class GradebookOut(BaseModel):
    evaluations: list[GradebookEvaluationOut]
    students: list[GradebookStudentOut]
