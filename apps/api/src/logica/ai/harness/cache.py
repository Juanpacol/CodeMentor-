"""Response cache (§9.1 "caché de respuestas frecuentes"): keyed on an exact
hash of (task, rendered prompt) — not true semantic similarity, which would
need its own embedding call and add cost/complexity disproportionate to the
win here. Many students hit the exact same first hint on a popular exercise,
so an exact-match cache already captures most of the savings."""

import hashlib
from typing import cast

from redis.asyncio import Redis

_CACHE_TTL_SECONDS = 60 * 60 * 24  # a day is enough: content changes invalidate naturally


def _cache_key(task: str, prompt: str) -> str:
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    return f"ai_cache:{task}:{digest}"


async def get_cached_response(redis: Redis, task: str, prompt: str) -> str | None:
    return cast(str | None, await redis.get(_cache_key(task, prompt)))


async def set_cached_response(redis: Redis, task: str, prompt: str, response: str) -> None:
    await redis.set(_cache_key(task, prompt), response, ex=_CACHE_TTL_SECONDS)
