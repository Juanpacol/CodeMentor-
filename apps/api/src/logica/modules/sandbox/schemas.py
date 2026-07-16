from typing import Any

from pydantic import BaseModel, Field


class PseIntSourceRequest(BaseModel):
    source: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)


class PseIntValidationOut(BaseModel):
    valid: bool
    error_line: int | None
    error_message: str | None

    model_config = {"from_attributes": True}


class PseIntTraceStepOut(BaseModel):
    line: int | None
    variables: dict[str, Any]


class PseIntRunOut(BaseModel):
    stdout: list[str]
    variables: dict[str, Any]
    trace: list[PseIntTraceStepOut]
