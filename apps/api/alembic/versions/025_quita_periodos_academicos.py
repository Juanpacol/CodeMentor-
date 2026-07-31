"""quita periodos académicos

Revision ID: 025
Revises: 024
Create Date: 2026-07-30 00:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: str | None = "024"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # `curriculum_plan_items.period_id` era la única otra FK hacia
    # `academic_periods` — apuntaba a una tabla inerte de la Fase 15 que ningún
    # servicio leía ni escribía (ver `content/models.py::Topic.estimated_sessions`),
    # así que se quita junto con la sección de periodos, sin backfill.
    op.drop_column("curriculum_plan_items", "period_id")
    op.drop_column("report_jobs", "period_id")
    op.drop_table("academic_periods")


def downgrade() -> None:
    op.create_table(
        "academic_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("report_jobs", sa.Column("period_id", sa.UUID(), nullable=True))
    op.add_column("curriculum_plan_items", sa.Column("period_id", sa.UUID(), nullable=True))
