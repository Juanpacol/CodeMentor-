"""The harness facade (§9.1): the ONLY entry point any skill/agent should
use to talk to an LLM. Composes, in strict order: render prompt → input
guardrail → budget check → cache lookup → model router (with fallback) →
output guardrail → cache write → usage/budget recording → trace → audit.

No caller (Fase 6 skills/agents, or anything else) may call
`ai.harness.router.complete` directly — going through here is what makes
every one of §9.1's requirements (guardrails, cost control, auditability)
apply uniformly instead of being re-implemented per-agent."""

from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.harness import budget, cache, tracing
from logica.ai.harness.guardrails import (
    OutputCheckResult,
    check_input_safety,
    check_output_safety,
)
from logica.ai.harness.prompts import render_prompt
from logica.ai.harness.router import complete as router_complete
from logica.ai.repository import record_interaction
from logica.core.errors import ValidationDomainError
from logica.modules.users.models import User


class OutputBlockedByGuardrailError(ValidationDomainError):
    pass


@dataclass(frozen=True)
class HarnessResult:
    text: str
    model: str
    from_cache: bool


async def complete_task(
    db: AsyncSession,
    redis: Redis,
    *,
    task: str,
    user: User,
    template_vars: dict[str, Any],
    untrusted_input: str | None = None,
    forbid_full_solution: bool = False,
) -> HarnessResult:
    """`untrusted_input` is whatever free text in `template_vars` actually
    came from the student (e.g. their latest answer) — only that slice is
    checked for prompt-injection, since the rest of the rendered prompt is
    our own trusted template content."""
    if untrusted_input:
        check_input_safety(untrusted_input)

    await budget.check_budget(redis, str(user.id))

    prompt = render_prompt(task, **template_vars)

    cached = await cache.get_cached_response(redis, task, prompt)
    if cached is not None:
        await record_interaction(
            db,
            institution_id=user.institution_id,
            user_id=user.id,
            task=task,
            model="cache",
            response_text=cached,
            prompt_tokens=0,
            completion_tokens=0,
            from_cache=True,
        )
        tracing.trace_completion(
            task=task,
            model="cache",
            prompt=prompt,
            output=cached,
            prompt_tokens=0,
            completion_tokens=0,
            from_cache=True,
            student_alias=str(user.id),
        )
        return HarnessResult(text=cached, model="cache", from_cache=True)

    result = await router_complete(task, messages=[{"role": "user", "content": prompt}])

    check_result: OutputCheckResult = check_output_safety(
        result.text, forbid_full_solution=forbid_full_solution
    )
    if not check_result.safe:
        await record_interaction(
            db,
            institution_id=user.institution_id,
            user_id=user.id,
            task=task,
            model=result.model,
            response_text=result.text,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            from_cache=False,
            blocked_by_guardrail=True,
            extra={"reason": check_result.reason},
        )
        raise OutputBlockedByGuardrailError(
            "La respuesta del asistente no pudo entregarse por una regla de seguridad. "
            "Intenta de nuevo o pide ayuda a tu docente."
        )

    await cache.set_cached_response(redis, task, prompt, result.text)
    await budget.record_usage(redis, str(user.id), result.prompt_tokens + result.completion_tokens)
    await record_interaction(
        db,
        institution_id=user.institution_id,
        user_id=user.id,
        task=task,
        model=result.model,
        response_text=result.text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        from_cache=False,
    )
    tracing.trace_completion(
        task=task,
        model=result.model,
        prompt=prompt,
        output=result.text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        from_cache=False,
        student_alias=str(user.id),
    )

    return HarnessResult(text=result.text, model=result.model, from_cache=False)
