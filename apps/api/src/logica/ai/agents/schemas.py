import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from logica.ai.agents.models import AgentName, TutorMessageRole
from logica.modules.exercises.models import ExerciseType
from logica.modules.guides.schemas import GuideOut


class AgentConfigOut(BaseModel):
    agent_name: AgentName
    enabled: bool


class AgentToggleRequest(BaseModel):
    enabled: bool


class TutorHintRequest(BaseModel):
    group_id: uuid.UUID
    exercise_id: uuid.UUID
    attempt_number: int = Field(ge=1)
    student_answer: str = Field(min_length=1)


class TutorMessageOut(BaseModel):
    id: uuid.UUID
    role: TutorMessageRole
    content: str
    created_at: datetime
    sources: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_validator("sources", mode="before")
    @classmethod
    def _default_sources(cls, value: list[str] | None) -> list[str]:
        return value or []


class ExerciseGenerateRequest(BaseModel):
    group_id: uuid.UUID
    topic_id: uuid.UUID
    exercise_type: ExerciseType


class GradingSuggestionRequest(BaseModel):
    evaluation_id: uuid.UUID
    answer_id: uuid.UUID
    rubric: str = Field(min_length=1)


class GradingSuggestionOut(BaseModel):
    answer_id: uuid.UUID
    ai_suggested_score: float | None
    ai_suggested_justification: str | None


class GroupSummaryOut(BaseModel):
    summary: str


class IntegrityCheckRequest(BaseModel):
    evaluation_id: uuid.UUID
    answer_id: uuid.UUID


class IntegrityAlertOut(BaseModel):
    id: uuid.UUID
    evaluation_answer_id: uuid.UUID
    suspicious: bool
    reasoning: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingExerciseOut(BaseModel):
    id: uuid.UUID
    title: str
    type: ExerciseType
    language_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingGradingSuggestionOut(BaseModel):
    answer_id: uuid.UUID
    evaluation_id: uuid.UUID
    exercise_title: str
    ai_suggested_score: float
    ai_suggested_justification: str


class PendingApprovalsOut(BaseModel):
    exercises: list[PendingExerciseOut]
    grading_suggestions: list[PendingGradingSuggestionOut]
    guides: list[GuideOut]
