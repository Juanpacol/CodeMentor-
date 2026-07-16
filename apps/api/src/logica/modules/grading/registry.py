from typing import Any

from logica.modules.exercises.models import ExerciseType
from logica.modules.grading.plugins import (
    ArguedResponseGrader,
    FillCodeGrader,
    FindErrorGrader,
    MultipleChoiceGrader,
    OrderLinesGrader,
    TraceVariablesGrader,
    TrueFalseGrader,
)
from logica.modules.grading.types import ExerciseGrader, GradeResult

EXERCISE_TYPE_REGISTRY: dict[ExerciseType, ExerciseGrader] = {
    ExerciseType.true_false: TrueFalseGrader(),
    ExerciseType.multiple_choice: MultipleChoiceGrader(),
    ExerciseType.fill_code: FillCodeGrader(),
    ExerciseType.find_error: FindErrorGrader(),
    ExerciseType.trace_variables: TraceVariablesGrader(),
    ExerciseType.order_lines: OrderLinesGrader(),
    ExerciseType.argued_response: ArguedResponseGrader(),
}


def grade_exercise(
    exercise_type: ExerciseType, content: dict[str, Any], answer: dict[str, Any]
) -> GradeResult:
    grader = EXERCISE_TYPE_REGISTRY[exercise_type]
    return grader.grade(content, answer)
