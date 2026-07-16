"""Grading for the `live_code` exercise type (§4.2): unlike the 7 RF-10
plugins in `plugins.py`, this needs I/O (a round trip to the sandbox), so it
lives outside the synchronous `ExerciseGrader` registry — callers branch on
`exercise.type == ExerciseType.live_code` and await this instead of calling
`grade_exercise`. See ADR for why this isn't forced into the sync protocol."""

from typing import Any

from logica.modules.grading.types import GradeResult
from logica.modules.sandbox.piston_client import SandboxUnavailableError, run_code


async def grade_live_code(content: dict[str, Any], answer: dict[str, Any]) -> GradeResult:
    source = answer.get("code")
    if not source or not str(source).strip():
        return GradeResult(score=0.0, correct=False, detail={"reason": "respuesta vacía"})

    test_cases: list[dict[str, Any]] = content.get("test_cases", [])
    if not test_cases:
        return GradeResult(score=0.0, correct=False, detail={"reason": "sin casos de prueba"})

    language = content.get("language", "python")
    version = content.get("version", "3.10.0")

    passed = 0
    case_details: list[dict[str, Any]] = []
    for case in test_cases:
        try:
            result = await run_code(
                language, version, str(source), stdin=str(case.get("stdin", ""))
            )
        except SandboxUnavailableError as exc:
            return GradeResult(
                score=0.0,
                correct=False,
                detail={"reason": "sandbox no disponible", "error": str(exc)},
            )

        expected = str(case.get("expected_stdout", "")).strip()
        actual = result.stdout.strip()
        ok = not result.timed_out and result.exit_code == 0 and actual == expected
        passed += int(ok)
        case_details.append({"passed": ok, "stderr": result.stderr if not ok else ""})

    score = passed / len(test_cases)
    return GradeResult(score=score, correct=score == 1.0, detail={"cases": case_details})
