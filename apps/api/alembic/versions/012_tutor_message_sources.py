"""tutor message sources

Revision ID: 012
Revises: 011
Create Date: 2026-07-25 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Atribución de fuente para el Agente Tutor (ai/agents/tutor.py::ask_hint):
    # guarda los títulos de RagDocument usados para fundamentar cada pista, para
    # que el estudiante/docente pueda verificar de qué material salió en vez de
    # confiar ciegamente en el LLM. Nullable porque los mensajes role=student no
    # tienen fuentes, y los mensajes tutor generados sin material disponible
    # tampoco.
    op.add_column("tutor_messages", sa.Column("sources", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tutor_messages", "sources")
