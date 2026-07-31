import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class AssignmentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic_id: uuid.UUID | None = None
    exercise_id: uuid.UUID | None = None
    due_at: datetime | None = None

    @model_validator(mode="after")
    def exactly_one_target(self) -> "AssignmentCreateRequest":
        """Mismo invariante que el `CheckConstraint` de la tabla. Se valida acá
        también para que el docente reciba un 422 explicativo en vez del error de
        integridad crudo de Postgres."""
        if (self.topic_id is None) == (self.exercise_id is None):
            raise ValueError("Asigna un tema o un ejercicio, no ambos ni ninguno")
        return self


class AssignmentUpdateRequest(BaseModel):
    """Solo lo que tiene sentido corregir después de asignar. Cambiar el tema o
    el ejercicio sería otra asignación, no una edición de esta."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    due_at: datetime | None = None


class AssignmentOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    title: str
    topic_id: uuid.UUID | None
    exercise_id: uuid.UUID | None
    due_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StudentAssignmentOut(BaseModel):
    """La vista del estudiante: la asignación más si ya la cumplió.

    `done` se resuelve contra sus envíos correctos de práctica, no se guarda: una
    columna de "entregado" sería una segunda fuente de verdad que habría que
    mantener sincronizada con cada envío.
    """

    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str
    title: str
    topic_id: uuid.UUID | None
    exercise_id: uuid.UUID | None
    due_at: datetime | None
    done: bool
    # Cuántos ejercicios cubre y cuántos van; para un ejercicio suelto es 1 y 0/1.
    total_exercises: int
    solved_exercises: int
