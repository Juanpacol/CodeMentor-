"""Eval harness (§9.4): a golden dataset per AI task, run through the real
harness pipeline (prompt rendering, guardrails, structured-output parsing)
with the model call itself replaced by the case's fixed `fake_model_output`
— 0 real tokens spent, but a change to a Jinja template or a guardrail that
breaks rendering/parsing for any of these ~30 cases fails CI. This is a
regression gate for `ai/prompts/`, not a judge of real model quality —
that's the separate `@pytest.mark.live` suite, run locally against real
providers."""

import os
from pathlib import Path
from typing import Any

import pytest
import yaml
from httpx import AsyncClient
from redis.asyncio import Redis

from logica.ai.agents.exercise_generator import ExerciseGenerationOutput
from logica.ai.agents.grading_assistant import GradingSuggestionOutput
from logica.ai.agents.guide_writer import GuideSectionOutput
from logica.ai.harness.harness import complete_task
from logica.ai.harness.router import CompletionResult
from logica.ai.harness.structured import complete_structured
from logica.db import get_session_factory
from logica.modules.users.models import Institution
from tests.integration.conftest import get_user_by_email, register_and_login

_DATASETS_DIR = Path(__file__).parent / "datasets"


def _load_cases(filename: str) -> list[dict[str, Any]]:
    data = yaml.safe_load((_DATASETS_DIR / filename).read_text())
    cases: list[dict[str, Any]] = data["cases"]
    return cases


def _check_text(text: str, checks: dict[str, Any]) -> None:
    if "min_length" in checks:
        assert len(text) >= checks["min_length"], f"salida demasiado corta: {text!r}"
    lowered = text.lower()
    for phrase in checks.get("must_not_contain", []):
        assert phrase.lower() not in lowered, (
            f"la pista filtró contenido prohibido {phrase!r} en {text!r}"
        )
    for phrase in checks.get("must_contain", []):
        assert phrase.lower() in lowered, f"falta contenido esperado {phrase!r} en {text!r}"


PROGRESSIVE_HINT_CASES = _load_cases("progressive_hint.yaml")
EXERCISE_GENERATION_CASES = _load_cases("exercise_generation.yaml")
GRADING_SUGGESTION_CASES = _load_cases("grading_suggestion.yaml")
GUIDE_GENERATION_CASES = _load_cases("guide_generation.yaml")

assert (
    len(PROGRESSIVE_HINT_CASES)
    + len(EXERCISE_GENERATION_CASES)
    + len(GRADING_SUGGESTION_CASES)
    + len(GUIDE_GENERATION_CASES)
    >= 30
), "§9.4 exige al menos 30 casos golden en total"


def _versions_under_test(task: str) -> list[int | None]:
    """`PROMPT_VERSIONS=progressive_hint=1,progressive_hint=2` (formato
    `tarea=version`, separado por comas) corre el dataset de esa tarea una
    vez por versión listada — así se compara la versión activa contra una
    candidata sin bifurcar el dataset. Sin la variable (el caso normal en
    CI), corre solo `[None]` (la versión activa), así que el costo no
    cambia. Ver `make evals-compare`."""
    raw = os.environ.get("PROMPT_VERSIONS", "")
    picked = [
        int(version)
        for entry_task, version in (pair.split("=") for pair in raw.split(",") if pair)
        if entry_task == task
    ]
    return picked or [None]


@pytest.mark.parametrize("prompt_version", _versions_under_test("progressive_hint"))
@pytest.mark.parametrize("case", PROGRESSIVE_HINT_CASES, ids=lambda c: c["id"])
async def test_progressive_hint_eval(
    case: dict[str, Any],
    prompt_version: int | None,
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    domain = institution.email_domains[0]
    await register_and_login(client, email=f"est@{domain}", role="student")
    user = await get_user_by_email(f"est@{domain}")

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text=case["fake_model_output"],
            model="eval/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    session_factory = get_session_factory()
    async with session_factory() as db:
        result = await complete_task(
            db,
            redis_client,
            task="progressive_hint",
            user=user,
            template_vars=case["template_vars"],
            untrusted_input=case["template_vars"].get("student_answer"),
            forbid_full_solution=True,
            prompt_version=prompt_version,
        )
        await db.commit()

    _check_text(result.text, case["checks"])


@pytest.mark.parametrize("case", EXERCISE_GENERATION_CASES, ids=lambda c: c["id"])
async def test_exercise_generation_eval(
    case: dict[str, Any],
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    domain = institution.email_domains[0]
    await register_and_login(client, email=f"doc@{domain}", role="teacher")
    user = await get_user_by_email(f"doc@{domain}")

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text=case["fake_model_output"],
            model="eval/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    session_factory = get_session_factory()
    async with session_factory() as db:
        output = await complete_structured(
            db,
            redis_client,
            task="exercise_generation",
            user=user,
            template_vars=case["template_vars"],
            output_model=ExerciseGenerationOutput,
        )
        await db.commit()

    checks = case["checks"]
    assert len(output.title) >= checks["title_min_length"]
    for key in checks["content_has_keys"]:
        assert key in output.content, f"falta la clave {key!r} en content: {output.content!r}"


@pytest.mark.parametrize("case", GRADING_SUGGESTION_CASES, ids=lambda c: c["id"])
async def test_grading_suggestion_eval(
    case: dict[str, Any],
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    domain = institution.email_domains[0]
    await register_and_login(client, email=f"doc@{domain}", role="teacher")
    user = await get_user_by_email(f"doc@{domain}")

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text=case["fake_model_output"],
            model="eval/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    session_factory = get_session_factory()
    async with session_factory() as db:
        output = await complete_structured(
            db,
            redis_client,
            task="grading_suggestion",
            user=user,
            template_vars=case["template_vars"],
            output_model=GradingSuggestionOutput,
        )
        await db.commit()

    checks = case["checks"]
    low, high = checks["score_range"]
    assert low <= output.suggested_score <= high
    assert len(output.justification) >= checks["justification_min_length"]


@pytest.mark.parametrize("prompt_version", _versions_under_test("guide_generation"))
@pytest.mark.parametrize("case", GUIDE_GENERATION_CASES, ids=lambda c: c["id"])
async def test_guide_generation_eval(
    case: dict[str, Any],
    prompt_version: int | None,
    client: AsyncClient,
    institution: Institution,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    domain = institution.email_domains[0]
    await register_and_login(client, email=f"doc@{domain}", role="teacher")
    user = await get_user_by_email(f"doc@{domain}")

    async def fake(task: str, messages: list[dict[str, str]]) -> CompletionResult:
        return CompletionResult(
            text=case["fake_model_output"],
            model="eval/fake",
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr("logica.ai.harness.harness.router_complete", fake)

    session_factory = get_session_factory()
    async with session_factory() as db:
        output = await complete_structured(
            db,
            redis_client,
            task="guide_generation",
            user=user,
            template_vars=case["template_vars"],
            output_model=GuideSectionOutput,
            prompt_version=prompt_version,
        )
        await db.commit()

    checks = case["checks"]
    assert len(output.heading) >= checks["heading_min_length"]
    assert len(output.body_md) >= checks["body_min_length"]
    # La plantilla prohíbe imágenes: la CSP del frontend (`img-src 'self' data:`)
    # las bloquearía y el estudiante vería un hueco roto en la guía.
    assert "![" not in output.body_md, f"la sección incluyó una imagen: {output.body_md!r}"
