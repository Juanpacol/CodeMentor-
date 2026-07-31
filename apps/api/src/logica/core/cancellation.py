"""Señal de cancelación cooperativa para los trabajos largos del worker.

En Redis y no en la base de datos porque el runner la consulta muchas veces por
tema —entre etapas y entre secciones de la guía— y un `db.refresh()` por consulta
multiplicaría las idas a Postgres dentro de un bucle que ya es lento. Un `GET` a
Redis cuesta microsegundos, así que se puede preguntar seguido; ese "seguido" es
justo lo que hace que cancelar se sienta inmediato.

Cooperativa y no `abort_job` de arq: matar el job a mitad de una escritura
dejaría guías en `generating` para siempre, sin ninguna forma de salir de ese
estado. El worker consulta la señal en puntos seguros y sale dejando las filas
consistentes. El estado en la BD (`status = cancelled`) sigue siendo la fuente de
verdad de cara al usuario; esto es solo el mecanismo de aviso.
"""

import uuid

from redis.asyncio import Redis

# Holgado a propósito: una corrida de 15 temas puede tardar más de una hora, y
# una señal que expira antes de que el worker llegue a leerla no cancela nada.
_TTL_SECONDS = 6 * 60 * 60


def _key(kind: str, entity_id: uuid.UUID) -> str:
    return f"cancel:{kind}:{entity_id}"


async def request_cancel(redis: Redis, kind: str, entity_id: uuid.UUID) -> None:
    """Pide la cancelación. Idempotente: pedirla dos veces es lo mismo que una."""
    await redis.set(_key(kind, entity_id), "1", ex=_TTL_SECONDS)


async def is_cancelled(redis: Redis, kind: str, entity_id: uuid.UUID) -> bool:
    return bool(await redis.exists(_key(kind, entity_id)))


async def clear_cancel(redis: Redis, kind: str, entity_id: uuid.UUID) -> None:
    """Se llama al terminar el job. Sin esto, reusar un id (o un TTL que sobreviva
    a un reintento) cancelaría una corrida nueva por una señal vieja."""
    await redis.delete(_key(kind, entity_id))
