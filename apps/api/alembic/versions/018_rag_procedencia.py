"""rag: procedencia de los documentos ingeridos de la web

Revision ID: 018
Revises: 017
Create Date: 2026-07-26 15:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: los documentos que ya existen los subió un docente a mano y no
    # tienen URL de origen. Sin estas dos columnas, un documento traído de la web
    # es indistinguible de uno que subió el docente, y `Guide.sources` solo lleva
    # títulos — el docente no podría verificar de dónde salió el material ni
    # atribuir contenido CC BY-SA, que es requisito de la licencia de Wikimedia.
    op.add_column("rag_documents", sa.Column("source_url", sa.String(length=1000), nullable=True))
    op.add_column(
        "rag_documents",
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rag_documents", "fetched_at")
    op.drop_column("rag_documents", "source_url")
