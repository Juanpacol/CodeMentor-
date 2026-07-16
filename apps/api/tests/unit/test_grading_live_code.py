import pytest

from logica.modules.grading.live_code import grade_live_code
from logica.modules.sandbox.piston_client import SandboxResult, SandboxUnavailableError


async def test_empty_code_scores_zero_without_calling_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_run_code(*args: object, **kwargs: object) -> SandboxResult:
        nonlocal called
        called = True
        raise AssertionError("no debería llamarse al sandbox con código vacío")

    monkeypatch.setattr("logica.modules.grading.live_code.run_code", fake_run_code)

    result = await grade_live_code(
        {"test_cases": [{"stdin": "", "expected_stdout": "hola"}]}, {"code": "   "}
    )
    assert result.score == 0.0
    assert result.correct is False
    assert called is False


async def test_no_test_cases_scores_zero() -> None:
    result = await grade_live_code({"test_cases": []}, {"code": "print('hola')"})
    assert result.score == 0.0


async def test_all_test_cases_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_code(*args: object, **kwargs: object) -> SandboxResult:
        return SandboxResult(stdout="42\n", stderr="", exit_code=0, timed_out=False)

    monkeypatch.setattr("logica.modules.grading.live_code.run_code", fake_run_code)

    result = await grade_live_code(
        {"test_cases": [{"stdin": "", "expected_stdout": "42"}]},
        {"code": "print(42)"},
    )
    assert result.score == 1.0
    assert result.correct is True


async def test_partial_test_cases_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = iter(
        [
            SandboxResult(stdout="4\n", stderr="", exit_code=0, timed_out=False),
            SandboxResult(stdout="wrong\n", stderr="", exit_code=0, timed_out=False),
        ]
    )

    async def fake_run_code(*args: object, **kwargs: object) -> SandboxResult:
        return next(calls)

    monkeypatch.setattr("logica.modules.grading.live_code.run_code", fake_run_code)

    result = await grade_live_code(
        {
            "test_cases": [
                {"stdin": "2 2", "expected_stdout": "4"},
                {"stdin": "3 3", "expected_stdout": "6"},
            ]
        },
        {"code": "..."},
    )
    assert result.score == 0.5
    assert result.correct is False


async def test_timeout_counts_as_failed_case(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_code(*args: object, **kwargs: object) -> SandboxResult:
        return SandboxResult(stdout="", stderr="", exit_code=None, timed_out=True)

    monkeypatch.setattr("logica.modules.grading.live_code.run_code", fake_run_code)

    result = await grade_live_code(
        {"test_cases": [{"stdin": "", "expected_stdout": "x"}]}, {"code": "while True: pass"}
    )
    assert result.score == 0.0


async def test_sandbox_unavailable_scores_zero_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_code(*args: object, **kwargs: object) -> SandboxResult:
        raise SandboxUnavailableError("piston caído")

    monkeypatch.setattr("logica.modules.grading.live_code.run_code", fake_run_code)

    result = await grade_live_code(
        {"test_cases": [{"stdin": "", "expected_stdout": "x"}]}, {"code": "print('x')"}
    )
    assert result.score == 0.0
    assert result.detail["reason"] == "sandbox no disponible"
