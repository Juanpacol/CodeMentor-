"""CLI de ingesta RAG (§9.4): carga un archivo de texto/Markdown como material
de referencia del curso para el Agente Tutor (Fase 6).

Uso:
    uv run python -m scripts.ingest_rag --institution <uuid> --title "Referencia PSeInt" \
        [--topic <uuid>] archivo.md

Desde la Fase 14 también existe `POST /ai/rag/documents` (multipart, docente/
admin) para subir material sin necesidad de acceso a este script.
"""

import argparse
import asyncio
import uuid
from pathlib import Path

import structlog

from logica.ai.rag.ingestion import ingest_document
from logica.db import get_session_factory

logger = structlog.get_logger()


async def _ingest(
    institution_id: uuid.UUID, title: str, text: str, topic_id: uuid.UUID | None
) -> None:
    session_factory = get_session_factory()
    async with session_factory() as db:
        document = await ingest_document(
            db, institution_id=institution_id, title=title, text=text, topic_id=topic_id
        )
        await db.commit()
    logger.info("document_ingested", id=str(document.id), title=title)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--institution", required=True, help="UUID de la institución")
    parser.add_argument("--title", required=True, help="Título del documento")
    parser.add_argument(
        "--topic", required=False, default=None, help="UUID del tema al que pertenece (opcional)"
    )
    parser.add_argument("file", type=Path, help="Ruta al archivo .md/.txt a ingerir")
    args = parser.parse_args()
    text = args.file.read_text(encoding="utf-8")

    asyncio.run(
        _ingest(
            uuid.UUID(args.institution),
            args.title,
            text,
            uuid.UUID(args.topic) if args.topic else None,
        )
    )


if __name__ == "__main__":
    main()
