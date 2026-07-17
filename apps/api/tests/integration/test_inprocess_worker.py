"""RUN_WORKER_IN_PROCESS (Fase 10, despliegue gratuito): en producción el
worker de arq corre como tarea asyncio dentro del mismo proceso de la API
en vez de como contenedor separado (el free tier de Render no incluye
background workers). Se prueba aislado, sin pasar por `create_app()`, para
no depender de la variable de entorno ni de la cache de `get_settings()`."""

import asyncio
from contextlib import suppress

from arq import create_pool
from arq.connections import RedisSettings

from logica.config import get_settings
from logica.workers.inprocess import build_in_process_worker


async def test_in_process_worker_processes_enqueued_job() -> None:
    worker = build_in_process_worker()
    task = asyncio.create_task(worker.async_run())
    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        job = await pool.enqueue_job("ping")
        assert job is not None
        result = await job.result(timeout=5)
        assert result == "pong"
    finally:
        await pool.aclose()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await worker.close()
