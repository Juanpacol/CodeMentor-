import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

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


class LaggingStudentOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    accuracy: float | None
    days_since_last_activity: int | None
    reason: str


class AcademicPeriodCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date


class AcademicPeriodOut(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date

    model_config = {"from_attributes": True}
