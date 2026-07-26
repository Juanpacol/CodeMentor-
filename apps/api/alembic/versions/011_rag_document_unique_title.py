"""rag document unique title

Revision ID: 011
Revises: 010
Create Date: 2026-07-25 19:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Robustece la ingesta RAG (ingestion.py::ingest_document) con identidad
    # por (institution_id, title): sin esto, una carrera entre dos requests
    # concurrentes de re-ingesta del mismo título podría crear un
    # RagDocument duplicado pese al chequeo "buscar-luego-actuar" en código.
    # ADVERTENCIA: falla si ya existen filas duplicadas (institution_id,
    # title) en un ambiente desplegado — verificar antes de aplicar ahí.
    op.create_unique_constraint(
        "uq_rag_document_institution_title", "rag_documents", ["institution_id", "title"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_rag_document_institution_title", "rag_documents", type_="unique")
