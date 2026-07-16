from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class GradeResult:
    """Uniform output of every exercise-type plugin (RE-05): the engine and
    its callers never need to know which of the 7 types (RF-10) produced it.
    `score` is normalized to [0, 1] so weighting/aggregation stays simple."""

    score: float
    correct: bool
    needs_manual_review: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score debe estar entre 0 y 1")


class ExerciseGrader(Protocol):
    """One plugin per exercise type (RF-10). `content` is the exercise's
    authored payload; `answer` is the student's submission. Pure — no I/O,
    no DB — so each type is trivially unit-testable in isolation."""

    def grade(self, content: dict[str, Any], answer: dict[str, Any]) -> GradeResult: ...
