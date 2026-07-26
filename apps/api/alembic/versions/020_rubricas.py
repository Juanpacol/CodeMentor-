"""rúbricas: corridas de generación automática de temario

Revision ID: 020
Revises: 019
Create Date: 2026-07-26 16:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: str | None = "019"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rubric_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("folder_id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("language_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("exercise_types", sa.JSON(), nullable=False),
        sa.Column("acquire_content", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "done",
                "partial",
                "failed",
                name="rubric_run_status",
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["folder_id"], ["guides_folders.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["guide_templates.id"]),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rubric_runs_institution_id"), "rubric_runs", ["institution_id"])
    op.create_index(op.f("ix_rubric_runs_group_id"), "rubric_runs", ["group_id"])

    op.create_table(
        "rubric_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("topic_name", sa.String(length=200), nullable=False),
        # `create_type=False`: el tipo `topic_level` ya existe desde la 002.
        # Sin esto, la migración muere con DuplicateObject.
        sa.Column(
            "level",
            postgresql.ENUM(
                "basico", "intermedio", "avanzado", name="topic_level", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("extra_urls", sa.JSON(), nullable=True),
        sa.Column("topic_id", sa.UUID(), nullable=True),
        sa.Column("guide_id", sa.UUID(), nullable=True),
        sa.Column("sources_ingested", sa.Integer(), nullable=False),
        sa.Column("exercises_created", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "acquiring",
                "writing_guide",
                "writing_exercises",
                "done",
                "failed",
                name="rubric_item_status",
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["run_id"], ["rubric_runs.id"], ondelete="CASCADE"),
        # SET NULL en ambas: borrar un tema o una guía no puede borrar el rastro
        # de que la rúbrica los generó — ese historial es lo que le explica al
        # docente qué produjo su corrida.
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["guide_id"], ["guides.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rubric_items_run_id"), "rubric_items", ["run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_rubric_items_run_id"), table_name="rubric_items")
    op.drop_table("rubric_items")
    op.drop_index(op.f("ix_rubric_runs_group_id"), table_name="rubric_runs")
    op.drop_index(op.f("ix_rubric_runs_institution_id"), table_name="rubric_runs")
    op.drop_table("rubric_runs")
    # Postgres no borra los tipos nativos al borrar la tabla que los usa.
    # `topic_level` NO se toca: lo creó la 002 y lo usan otras tablas.
    sa.Enum(name="rubric_item_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="rubric_run_status").drop(op.get_bind(), checkfirst=True)
