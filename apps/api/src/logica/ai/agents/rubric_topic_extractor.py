"""Interpreta el texto crudo extraído de una rúbrica institucional (PDF/DOCX,
ver `modules/rubrics/document_extraction.py`) y propone una lista estructurada
de temas para prellenar el formulario de rúbrica — un paso de *preview* puro,
sin interruptor de agente por grupo (como `pedagogical_feedback`), porque no
escribe nada en la DB del docente hasta que él confirma y lanza la corrida."""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from logica.ai.harness.structured import complete_structured
from logica.modules.rubrics.schemas import DocumentExtractionResult
from logica.modules.users.models import User


async def extract_topics_from_text(
    db: AsyncSession, redis: Redis, *, user: User, raw_text: str
) -> DocumentExtractionResult:
    return await complete_structured(
        db,
        redis,
        task="rubric_topic_extraction",
        user=user,
        template_vars={"raw_text": raw_text},
        untrusted_input=raw_text,
        output_model=DocumentExtractionResult,
    )
