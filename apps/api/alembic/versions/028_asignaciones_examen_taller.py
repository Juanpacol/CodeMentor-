"""asignaciones: agrega examen (evaluation_id) y taller (guide_id)

Revision ID: 028
Revises: 027
Create Date: 2026-07-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: str | None = "027"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assignments", sa.Column("evaluation_id", sa.UUID(), nullable=True))
    op.add_column("assignments", sa.Column("guide_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_assignments_evaluation_id", "assignments", "evaluations", ["evaluation_id"], ["id"]
    )
    op.create_foreign_key("fk_assignments_guide_id", "assignments", "guides", ["guide_id"], ["id"])

    op.drop_constraint("ck_assignment_topic_xor_exercise", "assignments", type_="check")
    op.create_check_constraint(
        "ck_assignment_exactly_one_target",
        "assignments",
        "(topic_id IS NOT NULL)::int + (exercise_id IS NOT NULL)::int + "
        "(evaluation_id IS NOT NULL)::int + (guide_id IS NOT NULL)::int = 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_assignment_exactly_one_target", "assignments", type_="check")
    op.create_check_constraint(
        "ck_assignment_topic_xor_exercise",
        "assignments",
        "(topic_id IS NULL) <> (exercise_id IS NULL)",
    )
    op.drop_constraint("fk_assignments_guide_id", "assignments", type_="foreignkey")
    op.drop_constraint("fk_assignments_evaluation_id", "assignments", type_="foreignkey")
    op.drop_column("assignments", "guide_id")
    op.drop_column("assignments", "evaluation_id")
