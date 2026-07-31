import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from logica.modules.progress.models import BadgeCriteria


class BadgeOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str
    criteria: BadgeCriteria
    language_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    earned_at: datetime

    model_config = {"from_attributes": True}


class TopicMasteryOut(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    submissions: int
    accuracy: float | None


class LanguageMasteryOut(BaseModel):
    language_id: uuid.UUID
    language_name: str
    submissions: int
    accuracy: float | None


class StudentProgressOut(BaseModel):
    student_id: uuid.UUID
    points: int
    badges: list[BadgeOut]
    mastery_by_topic: list[TopicMasteryOut]
    mastery_by_language: list[LanguageMasteryOut]


class DailyActivityOut(BaseModel):
    """Un día con actividad. Los días sin nada NO vienen en la lista: rellenar
    365 ceros triplicaría la respuesta y el frontend igual tiene que construir
    la rejilla completa del calendario."""

    date: date
    submissions: int
    correct: int


class StudentActivityOut(BaseModel):
    days: list[DailyActivityOut]
    current_streak: int
    longest_streak: int
    active_days: int
    total_submissions: int
    logins: int


class TodaySummaryOut(BaseModel):
    """Ítem 4 (dashboard estudiante): "mi progreso hoy" — un resumen del día,
    no un reemplazo de `/progress/me/activity` (que sigue siendo la serie
    completa para el heatmap)."""

    submissions: int
    correct: int
    current_streak: int
    badges_earned_today: list[BadgeOut]
    due_today: int
    due_tomorrow: int


class TimelineEventOut(BaseModel):
    kind: Literal["practice", "badge", "evaluation"]
    title: str
    detail: str
    occurred_at: datetime


class LaggingStudentOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    accuracy: float | None
    days_since_last_activity: int | None
    reason: str


