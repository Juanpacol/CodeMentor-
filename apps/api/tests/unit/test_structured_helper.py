from typing import Any

import pytest
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.harness.router import CompletionResult
from logica.ai.harness.structured import StructuredOutputError, complete_structured
from logica.modules.users.models import Role, User


class _Output(BaseModel):
    value: str
    score: float


def _make_user() -> User:
    import uuid

    return User(
        id=uuid.uuid4(),
        institution_id=uuid.uuid4(),
        email="doc@example.com",
        full_name="Docente",
        hashed_password="x",
        role=Role.teacher,
        is_active=True,
    )


class _FakeDb:
    def add(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def flush(self) -> None:
        pass


async def _no_op_complete_task_factory(response_texts: list[str]) -> Any:
    calls = {"count": 0}

    async def fake_complete_task(
        db: AsyncSession,
        redis: Redis,
        *,
        task: str,
        user: User,
        template_vars: dict[str, Any],
        untrusted_input: str | None = None,
        forbid_full_solution: bool = False,
    ) -> CompletionResult:
        text = response_texts[min(calls["count"], len(response_texts) - 1)]
        calls["count"] += 1
        return CompletionResult(text=text, model="fake", prompt_tokens=1, completion_tokens=1)

    return fake_complete_task, calls


async def test_valid_json_first_try(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, calls = await _no_op_complete_task_factory(['{"value": "ok", "score": 0.9}'])
    monkeypatch.setattr("logica.ai.harness.structured.complete_task", fake)

    result = await complete_structured(
        _FakeDb(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        task="exercise_generation",
        user=_make_user(),
        template_vars={},
        output_model=_Output,
    )
    assert result.value == "ok"
    assert result.score == 0.9
    assert calls["count"] == 1


async def test_json_wrapped_in_prose_is_extracted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, _ = await _no_op_complete_task_factory(
        ['Aquí tienes: {"value": "ok", "score": 0.5} ¡Saludos!']
    )
    monkeypatch.setattr("logica.ai.harness.structured.complete_task", fake)

    result = await complete_structured(
        _FakeDb(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        task="exercise_generation",
        user=_make_user(),
        template_vars={},
        output_model=_Output,
    )
    assert result.value == "ok"


async def test_retries_after_invalid_json_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, calls = await _no_op_complete_task_factory(
        ["esto no es json", '{"value": "recuperado", "score": 1.0}']
    )
    monkeypatch.setattr("logica.ai.harness.structured.complete_task", fake)

    result = await complete_structured(
        _FakeDb(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        task="exercise_generation",
        user=_make_user(),
        template_vars={},
        output_model=_Output,
        max_retries=1,
    )
    assert result.value == "recuperado"
    assert calls["count"] == 2


async def test_retries_after_schema_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, calls = await _no_op_complete_task_factory(
        ['{"value": "ok"}', '{"value": "ok", "score": 0.3}']
    )
    monkeypatch.setattr("logica.ai.harness.structured.complete_task", fake)

    result = await complete_structured(
        _FakeDb(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        task="exercise_generation",
        user=_make_user(),
        template_vars={},
        output_model=_Output,
        max_retries=1,
    )
    assert result.score == 0.3
    assert calls["count"] == 2


async def test_exhausting_retries_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, calls = await _no_op_complete_task_factory(["nunca es json válido"])
    monkeypatch.setattr("logica.ai.harness.structured.complete_task", fake)

    with pytest.raises(StructuredOutputError):
        await complete_structured(
            _FakeDb(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            task="exercise_generation",
            user=_make_user(),
            template_vars={},
            output_model=_Output,
            max_retries=1,
        )
    assert calls["count"] == 2
