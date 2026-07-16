import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    grade_or_shift: str | None = None


class GroupUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    grade_or_shift: str | None = None


class GroupOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    teacher_id: uuid.UUID
    name: str
    grade_or_shift: str | None
    invite_code: str
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class JoinGroupRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=16)


class CsvEnrollRowError(BaseModel):
    row_number: int
    raw_row: str
    reason: str


class CreatedAccount(BaseModel):
    email: str
    temporary_password: str


class CsvEnrollResult(BaseModel):
    enrolled: int
    already_enrolled: int
    created_accounts: list[CreatedAccount]
    errors: list[CsvEnrollRowError]
