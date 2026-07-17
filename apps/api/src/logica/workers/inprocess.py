from arq.worker import Worker, create_worker

from logica.workers.settings import WorkerSettings


def build_in_process_worker() -> Worker:
    """Construye el worker de arq para correr como tarea asyncio dentro del
    proceso de la API (ver `Settings.run_worker_in_process`).

    `handle_signals=False` es obligatorio: por defecto arq instala sus
    propios manejadores de SIGINT/SIGTERM, que pisarían los que ya instala
    uvicorn en el mismo proceso. El apagado ordenado lo hace el lifespan de
    FastAPI cancelando la tarea y llamando a `worker.close()`.
    """
    # arq's WorkerSettingsBase Protocol requires exact-Optional attribute
    # types (e.g. `redis_settings: RedisSettings | None`) for structural
    # typing; our WorkerSettings sets it unconditionally to a concrete
    # RedisSettings, which is what the arq CLI (`arq logica.workers.settings.
    # WorkerSettings`, used by Dockerfile.worker) already accepts at runtime.
    return create_worker(WorkerSettings, handle_signals=False)  # type: ignore[arg-type]
