"""Herramienta de depuración (uso manual, no parte del pipeline de producción):
proyecta los embeddings de `RagChunk` a 2D via PCA y exporta un JSON listo
para graficar, para poder inspeccionar visualmente si los chunks de un mismo
documento quedan agrupados en el espacio semántico.

Uso:
    uv run python -m scripts.visualize_embeddings --institution <uuid> > out.json
"""

import argparse
import asyncio
import json
import uuid

import numpy as np
from sqlalchemy import select

from logica.ai.rag.models import RagChunk, RagDocument
from logica.db import get_session_factory
from logica.modules.content.models import Topic  # noqa: F401
from logica.modules.users.models import Institution  # noqa: F401


def _pca_2d(vectors: np.ndarray) -> np.ndarray:
    """PCA vía SVD: centra los datos y proyecta sobre los 2 componentes de
    mayor varianza. Se implementa a mano con numpy (ya es dependencia del
    proyecto) en vez de agregar scikit-learn/umap-learn solo para un script
    de depuración de un solo uso."""
    centered = vectors - vectors.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    return centered @ vt[:2].T


async def _collect(institution_id: uuid.UUID) -> list[dict[str, object]]:
    session_factory = get_session_factory()
    async with session_factory() as db:
        result = await db.execute(
            select(
                RagChunk.id,
                RagChunk.document_id,
                RagChunk.chunk_index,
                RagChunk.content,
                RagChunk.embedding,
                RagDocument.title,
            )
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .where(RagDocument.institution_id == institution_id)
            .order_by(RagDocument.title, RagChunk.chunk_index)
        )
        rows = result.all()

    if not rows:
        return []

    vectors = np.array([row.embedding for row in rows], dtype=np.float64)
    coords = _pca_2d(vectors)

    return [
        {
            "chunk_id": str(row.id),
            "document_id": str(row.document_id),
            "document_title": row.title,
            "chunk_index": row.chunk_index,
            "content": row.content,
            "x": round(float(coords[i, 0]), 6),
            "y": round(float(coords[i, 1]), 6),
        }
        for i, row in enumerate(rows)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--institution", required=True, help="UUID de la institución")
    args = parser.parse_args()

    points = asyncio.run(_collect(uuid.UUID(args.institution)))
    print(json.dumps(points, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
