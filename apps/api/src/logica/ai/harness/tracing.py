"""Langfuse tracing (§9.4 "observabilidad dedicada"): every harness call is
traced with task, model, latency, cost and whether it was served from cache.
No-ops safely when LANGFUSE_PUBLIC_KEY/SECRET_KEY aren't set (local dev
without the `ai` compose profile, or CI) — tracing must never be a reason
the platform breaks.

Uses the Langfuse v3+ client directly (`start_observation`, not the removed
v2 `.trace()` method) since a context-manager `with` block doesn't fit this
module's fire-and-forget call shape."""

import structlog
from langfuse import Langfuse

from logica.config import get_settings

logger = structlog.get_logger()

_client: Langfuse | None = None
_client_initialized = False


def _get_client() -> Langfuse | None:
    global _client, _client_initialized
    if _client_initialized:
        return _client

    settings = get_settings()
    _client_initialized = True
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        _client = None
        return None

    _client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    return _client


def trace_completion(
    *,
    task: str,
    model: str,
    prompt: str,
    output: str,
    prompt_tokens: int,
    completion_tokens: int,
    from_cache: bool,
    student_alias: str,
) -> None:
    client = _get_client()
    if client is None:
        return

    try:
        generation = client.start_observation(
            name=task,
            as_type="generation",
            input=prompt,
            output=output,
            model=model,
            usage_details={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            metadata={"from_cache": from_cache, "student_alias": student_alias},
        )
        generation.end()
    except Exception as exc:  # noqa: BLE001 - tracing must never break a request
        logger.warning("langfuse_trace_failed", error=str(exc))


def reset_client_for_tests() -> None:
    """Test-only: forces re-evaluation of settings on the next call."""
    global _client, _client_initialized
    _client = None
    _client_initialized = False
