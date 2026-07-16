"""Strips the answer key from an exercise's `content` before it's ever sent to
a student — practicing or mid-evaluation. Mirrors `plugins.py` type-by-type
because each type hides a different field; kept separate from the grader
classes since this is a "what the student may see" concern, not a "how do we
score it" concern."""

from typing import Any

from logica.modules.exercises.models import ExerciseType

_SENSITIVE_FIELDS: dict[ExerciseType, tuple[str, ...]] = {
    ExerciseType.true_false: ("answer",),
    ExerciseType.multiple_choice: ("answer_index",),
    ExerciseType.fill_code: ("blanks",),
    ExerciseType.find_error: ("error_line", "error_kind"),
    ExerciseType.trace_variables: ("expected_trace",),
    ExerciseType.order_lines: ("correct_order",),
    ExerciseType.argued_response: (),
}


def strip_answer_key(exercise_type: ExerciseType, content: dict[str, Any]) -> dict[str, Any]:
    hidden = _SENSITIVE_FIELDS[exercise_type]
    return {key: value for key, value in content.items() if key not in hidden}
