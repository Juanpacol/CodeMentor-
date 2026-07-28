"""Orquestador de una corrida de rúbrica (Fase 17). Corre en el worker de arq.

Máquina de estados por tema, **secuencial a propósito**: el tier gratuito de Groq
limita peticiones por minuto, así que paralelizar los temas no acelera nada — solo
adelanta el 429 y manda todo al respaldo de Gemini.

    pending → acquiring → writing_guide → writing_exercises → done
                                                            ↘ failed

Se hace `commit` al cerrar cada etapa, no al final: la pantalla del docente hace
polling sobre estas filas y una corrida de minutos que solo escribe al terminar se
ve indistinguible de una colgada. Es el mismo criterio de
`reports/service.py::generate_group_report`, que commitea en cada transición.

Cada tema es su propia transacción (por el commit de cierre), así que un fallo de
SQL se lleva ese tema y no la corrida — por eso acá no hay `begin_nested()` y sí
un `rollback()` + relectura en el `except SQLAlchemyError`.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.exercise_generator import generate_exercises_for_guide
from logica.ai.agents.guide_writer import write_guide
from logica.ai.harness.budget import check_budget
from logica.ai.rag.acquire import AcquiredSource, acquire_for_topic
from logica.ai.rag.ingestion import ingest_document
from logica.core.cancellation import clear_cancel, is_cancelled
from logica.core.errors import (
    ConflictError,
    LogicaError,
    NotFoundError,
    ServiceUnavailableError,
)
from logica.modules.content.models import Topic
from logica.modules.content.service import create_topic, enable_topic_for_group
from logica.modules.exercises.models import ExerciseType
from logica.modules.guides.models import Guide, GuideOrigin, GuideStatus
from logica.modules.rubrics import repository
from logica.modules.rubrics.models import (
    RubricItem,
    RubricItemStatus,
    RubricRun,
    RubricRunStatus,
)
from logica.modules.users.models import User

logger = structlog.get_logger()

# Pausa entre temas. Cada tema son ~7 llamadas al modelo en ráfaga; el tier
# gratuito de Groq ronda las 30 por minuto. Sin esta pausa una rúbrica de 15
# temas se come la cuota en el primer tercio y el resto cae al respaldo.
ITEM_DELAY_SECONDS = 2.0

_DOCUMENT_TITLE_MAX = 300


def _document_title(topic_name: str, source: AcquiredSource) -> str:
    """La identidad de un `RagDocument` es `(institución, título)`, así que este
    nombre determina qué se pisa con qué.

    Lleva el tema por delante para que dos temas que citen el mismo artículo no
    se sobrescriban, y el origen al final porque Wikipedia y Wikibooks publican
    artículos distintos con títulos idénticos — sin eso el de Wikibooks
    reemplazaba en silencio al de Wikipedia y el conteo de fuentes mentía.
    """
    return f"{topic_name} — {source.title} ({source.origin})"[:_DOCUMENT_TITLE_MAX]


async def _ingest_sources(db: AsyncSession, run: RubricRun, item: RubricItem, topic: Topic) -> int:
    """Busca material y lo ingiere. Devuelve cuántos documentos distintos entraron.

    Nunca lanza: que Wikipedia responda 503 no puede tumbar el tema. Sin material
    la guía sale algo más genérica —`guide_writer` ya degrada bien con el RAG
    vacío— y eso es infinitamente mejor que no tener guía.
    """
    try:
        sources = await acquire_for_topic(
            item.topic_name,
            level=item.level.value,
            extra_urls=list(item.extra_urls or []),
        )
    except Exception:
        logger.exception("rubric_acquire_failed", run_id=str(run.id), topic=item.topic_name)
        return 0

    ingested = 0
    seen: set[str] = set()
    for source in sources:
        title = _document_title(item.topic_name, source)
        if title in seen:
            # Reingerir el mismo título borra y reescribe los chunks del anterior:
            # contarlo dos veces reportaría material que no existe.
            continue
        seen.add(title)
        try:
            await ingest_document(
                db,
                institution_id=run.institution_id,
                title=title,
                text=source.text,
                source_type="web",
                topic_id=topic.id,
                source_url=source.url,
            )
            ingested += 1
        except LogicaError as exc:
            logger.warning("rubric_ingest_failed", title=title, error=str(exc))
        except SQLAlchemyError:
            # Una sentencia fallida aborta la transacción abierta: hay que
            # deshacerla antes de intentar la siguiente fuente, o todo lo que
            # venga después falla en cascada con InFailedSqlTransaction.
            await db.rollback()
            logger.exception("rubric_ingest_row_failed", title=title)
    return ingested


class _Cancelled(Exception):
    """Señal interna de "el docente canceló".

    No es un `LogicaError` porque nunca sale de este módulo: el bucle la traduce
    a `status = cancelled`. Una excepción y no un valor de retorno para poder
    cortar desde cualquier profundidad del tema sin que cada etapa tenga que
    propagar un booleano.
    """


async def _checkpoint(redis: Redis, run_id: uuid.UUID) -> None:
    """Punto seguro para abandonar. Se llama entre etapas —nunca a mitad de una
    escritura— para que cancelar no deje guías atrapadas en `generating`."""
    if await is_cancelled(redis, "rubric_run", run_id):
        raise _Cancelled


async def _process_item(
    db: AsyncSession, redis: Redis, run: RubricRun, item: RubricItem, teacher: User
) -> None:
    """Un tema de principio a fin. Commitea en cada transición de etapa."""
    # 1. El tema. `create_topic` invalida el caché de temas por su cuenta.
    topic = await create_topic(
        db, redis, teacher, run.language_id, item.topic_name, item.level, item.order_index
    )
    await enable_topic_for_group(db, teacher, run.group_id, topic.id)
    item.topic_id = topic.id
    item.status = RubricItemStatus.acquiring
    await db.commit()

    # 2. Material de referencia.
    await _checkpoint(redis, run.id)
    if run.acquire_content:
        item.sources_ingested = await _ingest_sources(db, run, item, topic)
    item.status = RubricItemStatus.writing_guide
    await db.commit()
    await _checkpoint(redis, run.id)

    # 3. La guía. `write_guide` se llama en línea y no con otro `enqueue_job`
    # porque la rúbrica necesita saber si la guía salió antes de generarle
    # ejercicios, y arq no ofrece ninguna primitiva de join entre jobs.
    guide = Guide(
        institution_id=run.institution_id,
        folder_id=run.folder_id,
        template_id=run.template_id,
        topic_id=topic.id,
        created_by_id=teacher.id,
        title=f"{item.topic_name}",
        content_md="",
        origin=GuideOrigin.ai,
        status=GuideStatus.generating,
    )
    db.add(guide)
    await db.flush()
    item.guide_id = guide.id
    await db.commit()

    # La guía es la etapa larga (una llamada al modelo por sección), así que se
    # le pasa la señal para que corte entre secciones y no solo al terminarlas.
    await write_guide(
        db,
        redis,
        guide_id=guide.id,
        should_cancel=lambda: is_cancelled(redis, "rubric_run", run.id),
    )
    await db.commit()
    await db.refresh(guide)
    await _checkpoint(redis, run.id)

    if guide.status == GuideStatus.failed:
        # `write_guide` no propaga: marca la guía y devuelve. El motivo real ya
        # está en `error_message` y es más útil que uno genérico.
        item.status = RubricItemStatus.failed
        item.error_message = guide.error_message
        await db.commit()
        return

    item.status = RubricItemStatus.writing_exercises
    await db.commit()
    await _checkpoint(redis, run.id)

    # 4. Ejercicios de esa guía.
    exercises = await generate_exercises_for_guide(
        db,
        redis,
        teacher,
        guide_id=guide.id,
        exercise_types=[ExerciseType(value) for value in run.exercise_types],
    )
    item.exercises_created = len(exercises)
    item.status = RubricItemStatus.done
    await db.commit()


async def _mark_item_failed(
    db: AsyncSession,
    item_id: uuid.UUID,
    message: str,
    *,
    code: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Recarga el ítem antes de escribirlo. Después de un `rollback` los atributos
    del objeto quedan expirados, y refrescarlos desde dentro del `except` es el
    error que `content/service.py::enable_scheduled_topics` documenta."""
    item = await db.get(RubricItem, item_id)
    if item is None:  # pragma: no cover — la fila la creamos nosotros
        return
    item.status = RubricItemStatus.failed
    item.error_message = message[:1000]
    item.error_code = code
    item.error_details = details
    await db.commit()


async def _mark_item_cancelled(db: AsyncSession, item_id: uuid.UUID) -> None:
    """Sin `error_message`: cancelar no es un error, y ponerle uno haría que la
    UI lo pintara como incidente."""
    item = await db.get(RubricItem, item_id)
    if item is None:  # pragma: no cover — la fila la creamos nosotros
        return
    item.status = RubricItemStatus.cancelled
    await db.commit()


async def run_rubric(db: AsyncSession, redis: Redis, *, run_id: uuid.UUID) -> RubricRun:
    """Ejecuta la corrida completa.

    No filtra por `institution_id` al cargar la fila: el `run_id` viene de nuestro
    propio `enqueue_job`, no de entrada del usuario, y la validación de tenencia
    ya ocurrió al crearla (mismo criterio que `guide_writer.write_guide`).
    """
    run = await db.get(RubricRun, run_id)
    if run is None:
        raise NotFoundError("Corrida de rúbrica no encontrada")
    teacher = await db.get(User, run.requested_by_id)
    if teacher is None:
        raise NotFoundError("Docente responsable de la rúbrica no encontrado")

    run.status = RubricRunStatus.running
    await db.commit()

    items = await repository.list_items(db, run.id)
    completed = 0
    aborted_reason: str | None = None
    failures: list[tuple[str, str]] = []
    cancelled = False

    for index, item in enumerate(items):
        item_id = item.id
        if index:
            await asyncio.sleep(ITEM_DELAY_SECONDS)

        try:
            # Cancelación: la señal se consulta acá y también dentro del tema
            # (`_checkpoint`) y entre las secciones de la guía. Antes solo se
            # miraba en este punto, y como un tema son ~7 llamadas al modelo,
            # cancelar tardaba minutos en notarse y parecía no funcionar.
            await _checkpoint(redis, run.id)
            # Chequeo previo del presupuesto: `write_guide` no propaga el
            # `ConflictError` de la cuota (marca la guía como fallida y devuelve),
            # así que sin esto la corrida seguiría creando temas y guías vacías
            # hasta el último ítem en vez de parar en el primero.
            await check_budget(redis, str(teacher.id), teacher.role)
            await _process_item(db, redis, run, item, teacher)
            if item.status == RubricItemStatus.done:
                completed += 1
        except _Cancelled:
            # El tema a medias queda en `cancelled`, no en `failed`: no se cayó,
            # se le pidió parar. Lo ya escrito (tema, guía, ejercicios) se
            # conserva como borrador — ver `service.cancel_run`.
            await db.rollback()
            await _mark_item_cancelled(db, item_id)
            cancelled = True
            logger.info("rubric_run_cancelled_midway", run_id=str(run_id), topic=item.topic_name)
            break
        except (ConflictError, ServiceUnavailableError) as exc:
            # Condiciones globales: presupuesto agotado o cadena de proveedores
            # caída. Seguir con el siguiente tema repite el mismo fallo más lento.
            await db.rollback()
            await _mark_item_failed(db, item_id, exc.message, code=exc.code, details=exc.details)
            aborted_reason = exc.message
            failures.append((item.topic_name, exc.message))
            logger.warning("rubric_run_aborted", run_id=str(run_id), error=exc.message)
            break
        except LogicaError as exc:
            await db.rollback()
            await _mark_item_failed(db, item_id, exc.message, code=exc.code, details=exc.details)
            failures.append((item.topic_name, exc.message))
            logger.warning(
                "rubric_item_failed", run_id=str(run_id), topic=item.topic_name, error=exc.message
            )
        except SQLAlchemyError as exc:
            await db.rollback()
            await _mark_item_failed(
                db,
                item_id,
                "Error de base de datos al generar este tema",
                code="db_error",
                # El mensaje al docente se queda genérico a propósito, pero el
                # detalle tiene que existir en alguna parte consultable: antes
                # solo vivía en el log del servidor, al que él no tiene acceso.
                details={"exception": type(exc).__name__, "error": str(exc)[:1000]},
            )
            failures.append((item.topic_name, "error de base de datos"))
            logger.exception("rubric_item_row_failed", run_id=str(run_id), item_id=str(item_id))

    run = await db.get(RubricRun, run_id) or run
    if cancelled:
        # `cancelled` gana sobre el recálculo: con 8 de 10 temas hechos, marcar
        # `partial` borraría el hecho de que el docente pidió parar.
        run.status = RubricRunStatus.cancelled
        run.error_message = f"Cancelada por el docente — {completed} de {len(items)} temas listos"
    else:
        if completed == len(items):
            run.status = RubricRunStatus.done
        elif completed:
            # Ni `done` ni `failed`: 8 de 10 temas es el resultado común bajo los
            # límites del tier gratuito, y ambos extremos le mentirían al docente.
            run.status = RubricRunStatus.partial
        else:
            run.status = RubricRunStatus.failed
        # Antes esto solo se llenaba si la corrida abortó, así que una corrida
        # `partial` no decía en ninguna parte QUÉ temas se cayeron: el docente
        # tenía que abrir el detalle y revisar ítem por ítem.
        if aborted_reason:
            run.error_message = aborted_reason
        elif failures:
            resumen = "; ".join(f"{topic}: {motivo}" for topic, motivo in failures)
            run.error_message = f"{len(failures)} de {len(items)} temas fallaron — {resumen}"[:2000]
        else:
            run.error_message = None
    run.completed_at = datetime.now(UTC)
    await db.commit()

    # La señal ya cumplió: dejarla viva haría que un reintento de esta corrida
    # se cancelara solo al arrancar.
    await clear_cancel(redis, "rubric_run", run_id)

    logger.info(
        "rubric_run_finished",
        run_id=str(run_id),
        status=run.status.value,
        completed=completed,
        total=len(items),
    )
    return run
