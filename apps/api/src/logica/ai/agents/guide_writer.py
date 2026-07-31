"""Agente Creador de guías (Fase 16): escribe el contenido de una guía de clase
a partir de un tema y una `GuideTemplate`, fundamentándose en el material RAG del
propio curso. Toda salida queda como `status=draft` — invisible al estudiante
hasta que un docente la publica (§9.2, igual que el generador de ejercicios).

Corre en el worker de arq, nunca en el request path: son N llamadas al modelo
(una por sección) y superarían el timeout de la petición HTTP.
"""

import uuid
from collections.abc import Awaitable, Callable

import structlog
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.agents.models import AgentName
from logica.ai.harness.prompts import active_version
from logica.ai.harness.structured import complete_structured
from logica.ai.rag.retriever import RetrievedChunk, retrieve
from logica.core.errors import ConflictError, LogicaError, NotFoundError, ServiceUnavailableError
from logica.modules.content.repository import get_language, get_topic
from logica.modules.guides import repository
from logica.modules.guides.models import Guide, GuidesFolder, GuideTemplate
from logica.modules.users.models import User

logger = structlog.get_logger()

# Cuántos caracteres de cada sección ya escrita se le muestran al modelo como
# contexto de continuidad. Pasar los cuerpos completos haría crecer el prompt de
# forma cuadrática con el número de secciones (la sección 5 cargaría con las 4
# anteriores enteras); solo los encabezados no alcanzan para que no repita
# contenido. Este recorte es el punto medio.
_PREVIOUS_SECTION_PREVIEW_CHARS = 200


class GuideSectionOutput(BaseModel):
    heading: str = Field(min_length=2, max_length=200)
    body_md: str = Field(min_length=20)


def _format_reference_context(hits: list[RetrievedChunk]) -> str:
    """Mismo formato que `ai/skills/retrieve_context.py`. Se duplican estas dos
    líneas en vez de reusar el skill porque el skill devuelve solo el texto ya
    formateado y acá hacen falta también los `document_title` para llenar
    `Guide.sources` — cambiar su firma afectaría al Tutor sin necesidad."""
    return "\n\n".join(f"[Fuente: {hit.document_title}]\n{hit.content}" for hit in hits)


def _format_previous_sections(written: list[GuideSectionOutput]) -> str:
    return "\n\n".join(
        f"## {section.heading}\n{section.body_md[:_PREVIOUS_SECTION_PREVIEW_CHARS]}"
        for section in written
    )


def _assemble_markdown(written: list[GuideSectionOutput]) -> str:
    """El markdown se arma acá y no se le pide al modelo de una sola vez: el tier
    capaz corta cerca de los 8k tokens de salida, y una guía de 5 secciones los
    excede — el síntoma sería una guía truncada a mitad de frase. Un `##` por
    sección, que es el nivel que la plantilla del prompt le prohíbe usar."""
    return "\n\n".join(f"## {section.heading}\n\n{section.body_md}" for section in written)


class GuideCancelled(Exception):
    """El trabajo se abandonó por petición del usuario, no por un fallo.

    No hereda de `LogicaError` a propósito: no es un error de dominio que deba
    llegar al cliente como 4xx/5xx, y mezclarlo con ellos haría que el `except
    LogicaError` de abajo lo marcara como guía fallida.
    """


async def write_guide(
    db: AsyncSession,
    redis: Redis,
    *,
    guide_id: uuid.UUID,
    should_cancel: Callable[[], Awaitable[bool]] | None = None,
) -> Guide:
    """Rellena una `Guide` que ya existe en `status=generating`.

    `should_cancel` se consulta entre secciones. Es un callable y no un id
    porque quien cancela cambia según el contexto: en una rúbrica se cancela la
    corrida entera, y en una guía suelta, esa guía. Sin esto, cancelar durante
    la etapa más larga (una llamada al modelo por sección) no se notaba hasta
    que todas terminaban.

    No recibe un `User` de la petición porque corre en el worker: el docente
    responsable es `guide.created_by_id`, y es su presupuesto y su rastro de
    auditoría los que se usan. Tampoco filtra por `institution_id` al cargar la
    fila — el `guide_id` viene de nuestro propio `enqueue_job`, no de entrada del
    usuario, y la validación de tenencia ya ocurrió al crearla (mismo criterio
    que `reports/service.py::generate_group_report`)."""
    guide = await db.get(Guide, guide_id)
    if guide is None:
        raise NotFoundError("Guía no encontrada")

    try:
        written, sources, last_error = await _write_all_sections(
            db, redis, guide, should_cancel=should_cancel
        )
    except GuideCancelled:
        # Se conserva lo que alcanzó a escribirse: `cancelled` con contenido
        # parcial le sirve más al docente que descartar el trabajo entero.
        await repository.mark_guide_cancelled(db, guide)
        logger.info("guide_generation_cancelled", guide_id=str(guide_id))
        return guide
    except LogicaError as exc:
        # Un fallo que no es de una sección puntual (agente apagado, tema
        # borrado, docente inexistente): la guía entera no procede.
        logger.warning("guide_generation_aborted", guide_id=str(guide_id), error=str(exc))
        await repository.mark_guide_failed(
            db, guide, exc.message, error_code=exc.code, error_details=exc.details
        )
        return guide

    if not written:
        # Se propaga el motivo real de la última sección en vez de un genérico:
        # "alcanzaste el límite diario" o "la IA no está disponible" le dicen al
        # docente qué hacer, "el modelo no pudo redactar" no.
        await repository.mark_guide_failed(
            db,
            guide,
            last_error.message
            if last_error
            else "El modelo no pudo redactar ninguna sección de la guía.",
            error_code=last_error.code if last_error else None,
            error_details=last_error.details if last_error else None,
        )
        logger.warning("guide_generation_all_sections_failed", guide_id=str(guide_id))
        return guide

    await repository.mark_guide_drafted(
        db,
        guide,
        content_md=_assemble_markdown(written),
        sources=sorted(sources),
        prompt_version=active_version(AgentName.guide_writer.value),
    )
    logger.info(
        "guide_drafted",
        guide_id=str(guide_id),
        sections_written=len(written),
        sources=len(sources),
    )
    return guide


async def _write_all_sections(
    db: AsyncSession,
    redis: Redis,
    guide: Guide,
    *,
    should_cancel: Callable[[], Awaitable[bool]] | None = None,
) -> tuple[list[GuideSectionOutput], set[str], LogicaError | None]:
    folder = await db.get(GuidesFolder, guide.folder_id)
    if folder is None:
        raise NotFoundError("Carpeta de guías no encontrada")

    teacher = await db.get(User, guide.created_by_id)
    if teacher is None:
        raise NotFoundError("Docente responsable de la guía no encontrado")

    if guide.template_id is None:
        raise NotFoundError("La guía no tiene plantilla asociada")
    template = await db.get(GuideTemplate, guide.template_id)
    if template is None:
        raise NotFoundError("Plantilla de guía no encontrada")

    topic = await get_topic(db, guide.topic_id)
    if topic is None:
        raise NotFoundError("Tema no encontrado")
    language = await get_language(db, topic.language_id)
    if language is None:
        raise NotFoundError("Lenguaje no encontrado")

    written: list[GuideSectionOutput] = []
    sources: set[str] = set()
    # La excepción entera y no solo su `.message`: quien la persiste necesita
    # también el `code` y el `details` (qué proveedor falló, qué JSON no validó).
    last_error: LogicaError | None = None

    for section in template.sections:
        heading = section["heading"]
        # Antes de gastar otra llamada al modelo, no después: es lo que hace que
        # cancelar se sienta inmediato en vez de tardar lo que quede de guía.
        if should_cancel is not None and await should_cancel():
            raise GuideCancelled
        # Sin `db.begin_nested()` a propósito, aunque este sea un bucle que
        # escribe a la BD (la regla de CLAUDE.md). El SAVEPOINT hace falta cuando
        # una *sentencia* puede fallar y abortar la transacción abierta; acá todo
        # lo que puede fallar dentro del try es Python: `complete_structured`
        # levanta `StructuredOutputError` DESPUÉS de que sus `record_interaction`
        # se escribieron bien, y el presupuesto y la cadena de proveedores fallan
        # ANTES de tocar la BD. Un `begin_nested()` acá no aislaría nada y el
        # comentario que lo justificara sería falso. Si algún día se captura
        # `SQLAlchemyError` en este except, entonces sí hace falta.
        try:
            hits = await retrieve(
                db,
                guide.institution_id,
                f"{topic.name} {heading}",
                topic_id=guide.topic_id,
            )
            output = await complete_structured(
                db,
                redis,
                task=AgentName.guide_writer.value,
                user=teacher,
                template_vars={
                    "guide_title": guide.title,
                    "topic_name": topic.name,
                    "language": language.name,
                    "level": template.target_level.value,
                    "tone": template.tone,
                    "section_heading": heading,
                    "section_instructions": section["instructions"],
                    "reference_context": _format_reference_context(hits),
                    "previous_sections": _format_previous_sections(written),
                },
                output_model=GuideSectionOutput,
            )
        except (ConflictError, ServiceUnavailableError) as exc:
            # Condiciones GLOBALES, no de esta sección: presupuesto diario agotado
            # o toda la cadena de proveedores caída. Seguir el bucle repetiría el
            # mismo fallo en cada sección restante sin ninguna posibilidad de
            # éxito, así que se corta acá y se conserva lo ya escrito.
            logger.warning(
                "guide_generation_halted",
                guide_id=str(guide.id),
                section_heading=heading,
                error=str(exc),
            )
            last_error = exc
            break
        except LogicaError as exc:
            # Aislamiento por ítem: una sección que falla no invalida la guía.
            # Acá caen los fallos propios de esta sección — sobre todo
            # `StructuredOutputError`, cuando el modelo no produjo el JSON
            # esperado ni tras los reintentos de `complete_structured`.
            logger.warning(
                "guide_section_failed",
                guide_id=str(guide.id),
                section_heading=heading,
                error=str(exc),
            )
            last_error = exc
            continue

        written.append(output)
        sources.update(hit.document_title for hit in hits)

    return written, sources, last_error
