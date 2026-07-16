"""One grader class per RF-10 exercise type. Each is a small, independently
testable plugin behind the common `ExerciseGrader` protocol (RE-05) — adding
an eighth type later means writing one class and registering it, never
touching the others or the engine that calls them."""

from typing import Any

from logica.modules.grading.types import GradeResult


def _normalize_text(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


class TrueFalseGrader:
    def grade(self, content: dict[str, Any], answer: dict[str, Any]) -> GradeResult:
        expected = bool(content.get("answer"))
        submitted = answer.get("value")
        if submitted is None:
            return GradeResult(score=0.0, correct=False, detail={"reason": "respuesta vacía"})
        correct = bool(submitted) == expected
        return GradeResult(score=1.0 if correct else 0.0, correct=correct)


class MultipleChoiceGrader:
    def grade(self, content: dict[str, Any], answer: dict[str, Any]) -> GradeResult:
        expected = content.get("answer_index")
        submitted = answer.get("selected_index")
        if submitted is None:
            return GradeResult(score=0.0, correct=False, detail={"reason": "respuesta vacía"})
        correct = submitted == expected
        return GradeResult(score=1.0 if correct else 0.0, correct=correct)


class FillCodeGrader:
    def grade(self, content: dict[str, Any], answer: dict[str, Any]) -> GradeResult:
        expected_blanks: list[str] = content.get("blanks", [])
        submitted_blanks: list[str] = answer.get("values", []) or []

        if not expected_blanks:
            return GradeResult(score=0.0, correct=False, detail={"reason": "ejercicio sin blancos"})

        matches = 0
        for i, expected in enumerate(expected_blanks):
            submitted = submitted_blanks[i] if i < len(submitted_blanks) else None
            if _normalize_text(submitted) == _normalize_text(expected):
                matches += 1

        score = matches / len(expected_blanks)
        return GradeResult(score=score, correct=score == 1.0, detail={"matches": matches})


class FindErrorGrader:
    """Supports RF-28: for compiled languages the teacher can also tag whether
    the error is de sintaxis/lógica/tipos; matching the kind earns partial
    credit on top of matching the line."""

    def grade(self, content: dict[str, Any], answer: dict[str, Any]) -> GradeResult:
        expected_line = content.get("error_line")
        expected_kind = content.get("error_kind")
        submitted_line = answer.get("line")

        if submitted_line is None:
            return GradeResult(score=0.0, correct=False, detail={"reason": "respuesta vacía"})

        line_matches = submitted_line == expected_line

        if expected_kind is None:
            return GradeResult(score=1.0 if line_matches else 0.0, correct=line_matches)

        kind_matches = answer.get("kind") == expected_kind
        score = (0.7 if line_matches else 0.0) + (0.3 if kind_matches else 0.0)
        return GradeResult(score=score, correct=line_matches and kind_matches)


class TraceVariablesGrader:
    def grade(self, content: dict[str, Any], answer: dict[str, Any]) -> GradeResult:
        expected_trace: list[dict[str, Any]] = content.get("expected_trace", [])
        submitted_trace: list[dict[str, Any]] = answer.get("trace", []) or []

        if not expected_trace:
            return GradeResult(score=0.0, correct=False, detail={"reason": "sin trazado esperado"})

        matches = 0
        for i, expected_step in enumerate(expected_trace):
            submitted_step = submitted_trace[i] if i < len(submitted_trace) else None
            if submitted_step == expected_step:
                matches += 1

        score = matches / len(expected_trace)
        return GradeResult(score=score, correct=score == 1.0, detail={"matching_steps": matches})


class OrderLinesGrader:
    def grade(self, content: dict[str, Any], answer: dict[str, Any]) -> GradeResult:
        expected_order: list[int] = content.get("correct_order", [])
        submitted_order: list[int] | None = answer.get("order")

        if not expected_order:
            return GradeResult(score=0.0, correct=False, detail={"reason": "sin orden esperado"})
        if not submitted_order:
            return GradeResult(score=0.0, correct=False, detail={"reason": "respuesta vacía"})

        matches = sum(
            1
            for i, expected in enumerate(expected_order)
            if i < len(submitted_order) and submitted_order[i] == expected
        )
        score = matches / len(expected_order)
        return GradeResult(score=score, correct=score == 1.0)


class ArguedResponseGrader:
    """Open-ended responses always require a teacher's judgment (RF-12) — this
    plugin never asserts correctness, it only decides whether the queue needs
    to see it at all (an empty answer doesn't need a teacher's time)."""

    def grade(self, content: dict[str, Any], answer: dict[str, Any]) -> GradeResult:
        text = answer.get("text")
        if not text or not str(text).strip():
            return GradeResult(
                score=0.0,
                correct=False,
                needs_manual_review=False,
                detail={"reason": "respuesta vacía"},
            )
        return GradeResult(score=0.0, correct=False, needs_manual_review=True)
