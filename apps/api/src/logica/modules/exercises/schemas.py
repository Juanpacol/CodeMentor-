import uuid
from typing import Any

from pydantic import BaseModel, Field

from logica.modules.exercises.models import ExerciseOrigin, ExerciseStatus, ExerciseType


class ExerciseCreateRequest(BaseModel):
    language_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)
    type: ExerciseType
    content: dict[str, Any] = Field(default_factory=dict)
    status: ExerciseStatus = ExerciseStatus.published


class ExerciseUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    content: dict[str, Any] | None = None
    status: ExerciseStatus | None = None


class ExerciseOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    language_id: uuid.UUID
    title: str
    type: ExerciseType
    content: dict[str, Any]
    origin: ExerciseOrigin
    status: ExerciseStatus
    version: int

    model_config = {"from_attributes": True}
