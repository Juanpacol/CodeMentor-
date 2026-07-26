"""Response cache (§9.1 "caché de respuestas frecuentes"): keyed on an exact
hash of (task, rendered prompt) — not true semantic similarity, which would
need its own embedding call and add cost/complexity disproportionate to the
win here. Many students hit the exact same first hint on a popular exercise,
so an exact-match cache already captures most of the savings."""

import hashlib
from typing import cast

from redis.asyncio import Redis

_CACHE_TTL_SECONDS = 60 * 60 * 24  # a day is enough: content changes invalidate naturally


def _cache_key(task: str, prompt: str, version: int = 1) -> str:
    # La versión entra en la clave: dos versiones de una plantilla pueden
    # renderizar texto idéntico para un mismo input (una edición de solo
    # comentarios/espacios), y sin esto una eval que compara ambas versiones
    # se contaminaría con la respuesta cacheada de la otra.
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    return f"ai_cache:{task}:v{version}:{digest}"


async def get_cached_response(redis: Redis, task: str, prompt: str, version: int = 1) -> str | None:
    return cast(str | None, await redis.get(_cache_key(task, prompt, version)))


async def set_cached_response(
    redis: Redis, task: str, prompt: str, response: str, version: int = 1
) -> None:
    await redis.set(_cache_key(task, prompt, version), response, ex=_CACHE_TTL_SECONDS)
