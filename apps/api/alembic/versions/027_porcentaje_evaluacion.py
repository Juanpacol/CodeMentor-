"""agrega weight_percent a evaluations

Revision ID: 027
Revises: 026
Create Date: 2026-07-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: str | None = "026"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("evaluations", sa.Column("weight_percent", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluations", "weight_percent")
