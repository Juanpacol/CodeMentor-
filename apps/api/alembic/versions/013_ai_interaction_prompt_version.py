"""ai interaction prompt version

Revision ID: 013
Revises: 012
Create Date: 2026-07-26 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Versionado de prompts (§9.4, ítem 15): sin esta columna, una regresión
    # de calidad tras cambiar una plantilla es inatribuible — no hay forma de
    # saber qué texto produjo cada respuesta ya registrada.
    # server_default="1" porque todas las filas existentes se generaron con
    # la única versión que había antes de este cambio.
    op.add_column(
        "ai_interactions",
        sa.Column("prompt_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("ai_interactions", "prompt_version")
