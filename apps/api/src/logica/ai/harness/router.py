"""Model routing (§9.1): every AI call picks a model chain by *task*, not by
hardcoding a provider — a cheap/fast model for short hints, a more capable
one for generation, with automatic fallback if the first provider errors.

`_completion_fn` is a module-level indirection (not a class method) so tests
can monkeypatch a single call site and simulate provider failures/successes
deterministically, without hitting real APIs or spending tokens."""

from dataclasses import dataclass
from typing import Any, Literal

import litellm

from logica.config import get_settings

TaskTier = Literal["cheap", "capable"]

# Model chains, in fallback order. Real-world model IDs drift over time —
# these are current as of writing; swapping one is a one-line change here,
# never a change to callers.
_MODEL_CHAINS: dict[TaskTier, list[str]] = {
    "cheap": [
        "groq/llama-3.1-8b-instant",
        "gemini/gemini-1.5-flash",
        "ollama/llama3.1",
    ],
    "capable": [
        "groq/llama-3.3-70b-versatile",
        "gemini/gemini-1.5-pro",
        "ollama/llama3.1",
    ],
}

# Which tier each harness task uses. Fase 6 agents map onto these tasks.
TASK_TIERS: dict[str, TaskTier] = {
    "progressive_hint": "cheap",
    "pedagogical_feedback": "cheap",
    "summarize_group": "cheap",
    "exercise_generation": "capable",
    "grading_suggestion": "capable",
    "learning_analytics": "capable",
    "code_integrity": "capable",
}


class AllProvidersFailedError(Exception):
    def __init__(self, task: str, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Todos los proveedores fallaron para la tarea '{task}': {errors}")


@dataclass(frozen=True)
class CompletionResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


async def _completion_fn(model: str, messages: list[dict[str, str]]) -> Any:
    """The only place that calls litellm — swapped out wholesale in tests."""
    settings = get_settings()
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "timeout": 30}
    if model.startswith("ollama/"):
        kwargs["api_base"] = settings.ollama_base_url
    return await litellm.acompletion(**kwargs)


def _tier_for_task(task: str) -> TaskTier:
    return TASK_TIERS.get(task, "cheap")


async def complete(task: str, messages: list[dict[str, str]]) -> CompletionResult:
    """Tries each model in the task's chain in order, returning the first
    success. Raises AllProvidersFailedError only if every single one fails —
    the platform must keep working even if one LLM provider is down."""
    tier = _tier_for_task(task)
    chain = _MODEL_CHAINS[tier]

    errors: list[str] = []
    for model in chain:
        try:
            response = await _completion_fn(model, messages)
        except Exception as exc:  # noqa: BLE001 - any provider error triggers fallback
            errors.append(f"{model}: {exc}")
            continue

        choice = response.choices[0]
        usage = getattr(response, "usage", None)
        return CompletionResult(
            text=choice.message.content or "",
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    raise AllProvidersFailedError(task, errors)
