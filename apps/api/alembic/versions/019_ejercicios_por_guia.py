"""ejercicios: vínculo opcional con la guía que los originó

Revision ID: 019
Revises: 018
Create Date: 2026-07-26 15:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: el banco general de ejercicios (los que crea un docente a mano y
    # los que ya existen) no nace de ninguna guía. `topic_exercises` sigue siendo
    # el eje de organización por tema; esta FK solo responde "¿de qué guía salió
    # este ejercicio?", que es lo que un tema con dos guías no podría distinguir.
    op.add_column("exercises", sa.Column("guide_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_exercises_guide_id"), "exercises", ["guide_id"])
    # SET NULL y no CASCADE: un ejercicio ya publicado y adjunto a una evaluación
    # no puede desaparecer porque se borró la guía de la que nació — se quedaría
    # sin enunciado una evaluación que un estudiante ya presentó.
    op.create_foreign_key(
        "fk_exercises_guide_id",
        "exercises",
        "guides",
        ["guide_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_exercises_guide_id", "exercises", type_="foreignkey")
    op.drop_index(op.f("ix_exercises_guide_id"), table_name="exercises")
    op.drop_column("exercises", "guide_id")
