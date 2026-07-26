"""ai interaction cost

Revision ID: 014
Revises: 013
Create Date: 2026-07-26 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Costo estimado por interacción (ítem 14): hoy solo hay tokens, que no
    # son comparables entre modelos — 1000 tokens de gemini-1.5-pro cuestan
    # ~25x lo mismo en llama-3.1-8b-instant. Numeric y no Float porque sumar
    # miles de floats para una cifra con forma de dinero acumula deriva.
    # server_default="0" porque las filas existentes se generaron antes de
    # que este cálculo existiera.
    op.add_column(
        "ai_interactions",
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
    )
    # El dashboard de costo siempre filtra institución + rango de fechas.
    op.create_index(
        "ix_ai_interactions_institution_created",
        "ai_interactions",
        ["institution_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_interactions_institution_created", table_name="ai_interactions")
    op.drop_column("ai_interactions", "cost_usd")
