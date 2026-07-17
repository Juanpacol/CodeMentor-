import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from logica.modules.evaluations.models import AttemptStatus, EvaluationMode
from logica.modules.exercises.models import ExerciseType


class EvaluationCreateRequest(BaseModel):
    group_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)
    mode: EvaluationMode
    up_to_topic_id: uuid.UUID | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    is_ranked: bool = False
    exercise_ids: list[uuid.UUID] = Field(min_length=1)


class EvaluationOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    group_id: uuid.UUID
    teacher_id: uuid.UUID
    title: str
    mode: EvaluationMode
    up_to_topic_id: uuid.UUID | None
    duration_minutes: int | None
    is_ranked: bool

    model_config = {"from_attributes": True}


class TakeExerciseOut(BaseModel):
    evaluation_exercise_id: uuid.UUID
    order_index: int
    points: float
    exercise_id: uuid.UUID
    type: ExerciseType
    title: str
    content: dict[str, Any]


class TakeEvaluationOut(BaseModel):
    evaluation: EvaluationOut
    attempt_id: uuid.UUID
    started_at: datetime
    deadline: datetime | None
    exercises: list[TakeExerciseOut]


class SubmitAnswerRequest(BaseModel):
    evaluation_exercise_id: uuid.UUID
    answer: dict[str, Any] = Field(default_factory=dict)


class QuestionResultOut(BaseModel):
    evaluation_exercise_id: uuid.UUID
    score: float
    correct: bool
    needs_manual_review: bool
    manual_score: float | None


class AttemptResultOut(BaseModel):
    attempt_id: uuid.UUID
    status: AttemptStatus
    total_score: float | None
    max_score: float
    answers: list[QuestionResultOut]


class ManualReviewItemOut(BaseModel):
    answer_id: uuid.UUID
    attempt_id: uuid.UUID
    student_id: uuid.UUID
    evaluation_exercise_id: uuid.UUID
    exercise_title: str
    answer: dict[str, Any]


class ManualReviewSubmitRequest(BaseModel):
    score: float = Field(ge=0.0, le=1.0)


class AnswerSummaryOut(BaseModel):
    answer_id: uuid.UUID
    evaluation_exercise_id: uuid.UUID
    student_id: uuid.UUID
    score: float
    correct: bool
    needs_manual_review: bool
    manual_score: float | None
    ai_suggested_score: float | None


class RankingEntryOut(BaseModel):
    student_id: uuid.UUID
    total_score: float


class PracticeExerciseOut(BaseModel):
    id: uuid.UUID
    language_id: uuid.UUID
    type: ExerciseType
    title: str
    content: dict[str, Any]


class PracticeSubmitRequest(BaseModel):
    group_id: uuid.UUID
    answer: dict[str, Any] = Field(default_factory=dict)


class PracticeResultOut(BaseModel):
    score: float
    correct: bool
    needs_manual_review: bool
