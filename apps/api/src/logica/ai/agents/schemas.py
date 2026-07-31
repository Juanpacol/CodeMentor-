import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from logica.ai.agents.models import TutorMessageRole
from logica.modules.exercises.models import ExerciseType
from logica.modules.guides.schemas import GuideOut


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


class ExerciseVariantsRequest(BaseModel):
    # Tope de 4: cada variante es una llamada al modelo, y esto corre en el
    # request path (a diferencia del lote de guías) — 4 mantiene la espera
    # del docente razonable.
    count: int = Field(default=3, ge=1, le=4)


class ExerciseVariantOut(BaseModel):
    """Preview puro: no tiene `id` porque no se persiste hasta que el docente
    la acepta (vía el `POST /exercises` que ya existe)."""

    title: str
    content: dict[str, Any]


class GuideExercisesRequest(BaseModel):
    # Tope de 6: son 6 llamadas al modelo en un mismo lote, y el free tier de
    # Groq limita peticiones por minuto. Sin tope, pedir los 8 tipos de una guía
    # tras otra agota la cuota y todo cae al respaldo de Gemini.
    exercise_types: list[ExerciseType] = Field(min_length=1, max_length=6)


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
