"""Structured-output helper for the 5 Fase 6 agents (RF-30..35).

We deliberately do NOT use `pydantic_ai.Agent`/`Model` here (see
`docs/adr/004-agentes-sin-runtime-de-pydantic-ai.md`): every one of these
agents performs a single text-in/structured-out transformation with no
multi-step tool use, so a custom `pydantic_ai.models.Model` adapter would
only add an indirection layer between `complete_task()` and the model
without letting us skip any of the harness's own bookkeeping. Instead, each
agent renders a prompt whose template ends in "responde solo con un JSON de
esta forma", calls `complete_task()` — getting guardrails/budget/cache/audit
for free — and this helper parses+validates the result, retrying with a
corrective follow-up if the model's JSON doesn't validate the first time."""

import json
from typing import Any

from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.harness.harness import complete_task
from logica.core.errors import ValidationDomainError
from logica.modules.users.models import User


class StructuredOutputError(ValidationDomainError):
    pass


def _extract_json(text: str) -> str:
    """Models occasionally wrap JSON in prose or code fences despite
    instructions; take the substring between the first `{` and the last `}`
    rather than failing outright on decorated output."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]


async def complete_structured[T: BaseModel](
    db: AsyncSession,
    redis: Redis,
    *,
    task: str,
    user: User,
    template_vars: dict[str, Any],
    output_model: type[T],
    untrusted_input: str | None = None,
    max_retries: int = 2,
) -> T:
    """Structured-output tasks (exercise_generation, grading_suggestion,
    code_integrity) are only ever invoked by teacher-facing flows, never
    mid-evaluation for a student, so `forbid_full_solution` is always False
    here — there is no "solution" to withhold in a JSON-shaped response."""
    last_error_message: str | None = None
    vars_for_call = dict(template_vars)

    for attempt in range(max_retries + 1):
        if last_error_message is not None:
            vars_for_call["previous_error"] = (
                f"Tu respuesta anterior no cumplió el formato esperado: {last_error_message}. "
                "Responde de nuevo ÚNICAMENTE con el JSON solicitado."
            )

        result = await complete_task(
            db,
            redis,
            task=task,
            user=user,
            template_vars=vars_for_call,
            untrusted_input=untrusted_input if attempt == 0 else None,
        )

        try:
            payload = json.loads(_extract_json(result.text))
            return output_model.model_validate(payload)
        except json.JSONDecodeError as exc:
            last_error_message = f"no era JSON válido ({exc})"
            continue
        except ValidationError as exc:
            last_error_message = str(exc)
            continue

    raise StructuredOutputError(
        f"El modelo no produjo una salida válida para la tarea '{task}' "
        f"tras {max_retries + 1} intentos."
    )
