import pytest
from hypothesis import given
from hypothesis import strategies as st

from logica.modules.exercises.models import ExerciseType
from logica.modules.grading.registry import grade_exercise
from logica.modules.grading.types import GradeResult


class TestTrueFalse:
    @pytest.mark.parametrize(
        ("expected", "submitted", "correct"),
        [
            (True, True, True),
            (True, False, False),
            (False, False, True),
            (False, True, False),
        ],
    )
    def test_matrix(self, expected: bool, submitted: bool, correct: bool) -> None:
        result = grade_exercise(ExerciseType.true_false, {"answer": expected}, {"value": submitted})
        assert result.correct is correct
        assert result.score == (1.0 if correct else 0.0)

    def test_empty_answer(self) -> None:
        result = grade_exercise(ExerciseType.true_false, {"answer": True}, {"value": None})
        assert result.correct is False
        assert result.score == 0.0


class TestMultipleChoice:
    def test_correct_selection(self) -> None:
        result = grade_exercise(
            ExerciseType.multiple_choice, {"answer_index": 2}, {"selected_index": 2}
        )
        assert result.correct is True

    def test_incorrect_selection(self) -> None:
        result = grade_exercise(
            ExerciseType.multiple_choice, {"answer_index": 2}, {"selected_index": 0}
        )
        assert result.correct is False
        assert result.score == 0.0

    def test_empty_answer(self) -> None:
        result = grade_exercise(
            ExerciseType.multiple_choice, {"answer_index": 2}, {"selected_index": None}
        )
        assert result.correct is False


class TestFillCode:
    def test_all_blanks_correct(self) -> None:
        result = grade_exercise(
            ExerciseType.fill_code,
            {"blanks": ["Mientras", "FinMientras"]},
            {"values": ["mientras", "  FinMientras  "]},
        )
        assert result.correct is True
        assert result.score == 1.0

    def test_partial_credit(self) -> None:
        result = grade_exercise(
            ExerciseType.fill_code,
            {"blanks": ["Mientras", "FinMientras"]},
            {"values": ["Mientras", "Otra cosa"]},
        )
        assert result.correct is False
        assert result.score == 0.5

    def test_missing_values_treated_as_wrong(self) -> None:
        result = grade_exercise(
            ExerciseType.fill_code, {"blanks": ["Mientras", "FinMientras"]}, {"values": []}
        )
        assert result.score == 0.0

    def test_malformed_no_blanks_in_content(self) -> None:
        result = grade_exercise(ExerciseType.fill_code, {}, {"values": ["algo"]})
        assert result.correct is False
        assert result.score == 0.0


class TestFindError:
    def test_line_only_correct(self) -> None:
        result = grade_exercise(ExerciseType.find_error, {"error_line": 5}, {"line": 5})
        assert result.correct is True
        assert result.score == 1.0

    def test_line_only_incorrect(self) -> None:
        result = grade_exercise(ExerciseType.find_error, {"error_line": 5}, {"line": 3})
        assert result.correct is False

    def test_line_and_kind_full_credit(self) -> None:
        result = grade_exercise(
            ExerciseType.find_error,
            {"error_line": 5, "error_kind": "sintaxis"},
            {"line": 5, "kind": "sintaxis"},
        )
        assert result.correct is True
        assert result.score == 1.0

    def test_line_correct_kind_wrong_partial_credit(self) -> None:
        result = grade_exercise(
            ExerciseType.find_error,
            {"error_line": 5, "error_kind": "sintaxis"},
            {"line": 5, "kind": "logica"},
        )
        assert result.correct is False
        assert result.score == pytest.approx(0.7)

    def test_empty_answer(self) -> None:
        result = grade_exercise(ExerciseType.find_error, {"error_line": 5}, {"line": None})
        assert result.correct is False
        assert result.score == 0.0


class TestTraceVariables:
    def test_full_match(self) -> None:
        expected = [{"x": "1"}, {"x": "2"}]
        result = grade_exercise(
            ExerciseType.trace_variables, {"expected_trace": expected}, {"trace": expected}
        )
        assert result.correct is True
        assert result.score == 1.0

    def test_partial_match(self) -> None:
        result = grade_exercise(
            ExerciseType.trace_variables,
            {"expected_trace": [{"x": "1"}, {"x": "2"}]},
            {"trace": [{"x": "1"}, {"x": "wrong"}]},
        )
        assert result.score == 0.5
        assert result.correct is False

    def test_empty_trace(self) -> None:
        result = grade_exercise(
            ExerciseType.trace_variables, {"expected_trace": [{"x": "1"}]}, {"trace": []}
        )
        assert result.score == 0.0

    @given(
        steps=st.lists(
            st.dictionaries(st.text(min_size=1, max_size=3), st.text()), min_size=1, max_size=5
        )
    )
    def test_identical_trace_always_scores_full(self, steps: list[dict[str, str]]) -> None:
        result = grade_exercise(
            ExerciseType.trace_variables, {"expected_trace": steps}, {"trace": steps}
        )
        assert result.score == 1.0
        assert result.correct is True


class TestOrderLines:
    def test_exact_order_correct(self) -> None:
        result = grade_exercise(
            ExerciseType.order_lines, {"correct_order": [2, 0, 1]}, {"order": [2, 0, 1]}
        )
        assert result.correct is True
        assert result.score == 1.0

    def test_partial_order(self) -> None:
        result = grade_exercise(
            ExerciseType.order_lines, {"correct_order": [0, 1, 2]}, {"order": [0, 2, 1]}
        )
        assert result.correct is False
        assert result.score == pytest.approx(1 / 3)

    def test_empty_answer(self) -> None:
        result = grade_exercise(
            ExerciseType.order_lines, {"correct_order": [0, 1, 2]}, {"order": None}
        )
        assert result.score == 0.0

    @given(order=st.permutations([0, 1, 2, 3, 4]))
    def test_any_permutation_matched_against_itself_is_perfect(self, order: list[int]) -> None:
        result = grade_exercise(
            ExerciseType.order_lines, {"correct_order": order}, {"order": order}
        )
        assert result.score == 1.0
        assert result.correct is True


class TestArguedResponse:
    def test_nonempty_answer_needs_manual_review(self) -> None:
        result = grade_exercise(
            ExerciseType.argued_response, {"prompt": "Explica"}, {"text": "Mi argumento..."}
        )
        assert result.needs_manual_review is True

    def test_empty_answer_does_not_need_review(self) -> None:
        result = grade_exercise(ExerciseType.argued_response, {"prompt": "Explica"}, {"text": ""})
        assert result.needs_manual_review is False
        assert result.correct is False

    def test_whitespace_only_answer_does_not_need_review(self) -> None:
        result = grade_exercise(
            ExerciseType.argued_response, {"prompt": "Explica"}, {"text": "   "}
        )
        assert result.needs_manual_review is False


def test_grade_result_rejects_out_of_range_score() -> None:
    with pytest.raises(ValueError):
        GradeResult(score=1.5, correct=True)
