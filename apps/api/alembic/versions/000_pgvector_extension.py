"""enable pgvector extension

Revision ID: 000
Revises:
Create Date: 2026-07-16

"""

from collections.abc import Sequence

from alembic import op

revision: str = "000"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
