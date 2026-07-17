from dataclasses import dataclass
from typing import Any

import pytest

from logica.ai.harness.router import AllProvidersFailedError, complete


@dataclass
class _FakeUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class _FakeMessage:
    content: str


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]
    usage: _FakeUsage


def _fake_response(text: str, prompt_tokens: int = 10, completion_tokens: int = 5) -> _FakeResponse:
    return _FakeResponse(
        choices=[_FakeChoice(message=_FakeMessage(content=text))],
        usage=_FakeUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


async def test_first_model_success_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_completion_fn(model: str, messages: list[dict[str, str]]) -> Any:
        calls.append(model)
        return _fake_response("hola")

    monkeypatch.setattr("logica.ai.harness.router._completion_fn", fake_completion_fn)

    result = await complete("progressive_hint", [{"role": "user", "content": "hola"}])
    assert result.text == "hola"
    assert len(calls) == 1
    assert result.model == calls[0]


async def test_falls_back_when_first_provider_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_completion_fn(model: str, messages: list[dict[str, str]]) -> Any:
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("groq unavailable")
        return _fake_response("respuesta de respaldo")

    monkeypatch.setattr("logica.ai.harness.router._completion_fn", fake_completion_fn)

    result = await complete("progressive_hint", [{"role": "user", "content": "hola"}])
    assert result.text == "respuesta de respaldo"
    assert len(calls) == 2


async def test_all_providers_failing_raises_with_all_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_completion_fn(model: str, messages: list[dict[str, str]]) -> Any:
        raise RuntimeError(f"{model} down")

    monkeypatch.setattr("logica.ai.harness.router._completion_fn", fake_completion_fn)

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await complete("progressive_hint", [{"role": "user", "content": "hola"}])
    assert len(exc_info.value.errors) == 3


async def test_cheap_task_uses_cheap_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    used_models: list[str] = []

    async def fake_completion_fn(model: str, messages: list[dict[str, str]]) -> Any:
        used_models.append(model)
        return _fake_response("ok")

    monkeypatch.setattr("logica.ai.harness.router._completion_fn", fake_completion_fn)
    await complete("progressive_hint", [{"role": "user", "content": "x"}])
    assert "8b" in used_models[0] or "flash" in used_models[0]


async def test_capable_task_uses_capable_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    used_models: list[str] = []

    async def fake_completion_fn(model: str, messages: list[dict[str, str]]) -> Any:
        used_models.append(model)
        return _fake_response("ok")

    monkeypatch.setattr("logica.ai.harness.router._completion_fn", fake_completion_fn)
    await complete("exercise_generation", [{"role": "user", "content": "x"}])
    assert "70b" in used_models[0] or "pro" in used_models[0]


async def test_unknown_task_defaults_to_cheap_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    used_models: list[str] = []

    async def fake_completion_fn(model: str, messages: list[dict[str, str]]) -> Any:
        used_models.append(model)
        return _fake_response("ok")

    monkeypatch.setattr("logica.ai.harness.router._completion_fn", fake_completion_fn)
    await complete("una_tarea_no_registrada", [{"role": "user", "content": "x"}])
    assert "8b" in used_models[0] or "flash" in used_models[0]
