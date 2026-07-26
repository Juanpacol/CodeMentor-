"""guías: carpetas, plantillas y guías

Revision ID: 015
Revises: 014
Create Date: 2026-07-26 12:27:53.039764

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: str | None = "014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# `guide_templates.target_level` reusa el enum nativo `topic_level` que creó la
# migración 002 — es el mismo vocabulario (básico/intermedio/avanzado) y un nivel
# nuevo debe entrar por un solo ALTER TYPE, no por dos tipos que se desincronizan.
# `create_type=False` es obligatorio: el `sa.Enum(...)` que genera autogenerate
# emitiría un CREATE TYPE y la migración fallaría con DuplicateObject.
topic_level = postgresql.ENUM(
    "basico", "intermedio", "avanzado", name="topic_level", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "guide_templates",
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("tone", sa.String(length=50), nullable=False),
        sa.Column("target_level", topic_level, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "institution_id", "name", "version", name="uq_guide_template_name_version"
        ),
    )
    op.create_index(
        op.f("ix_guide_templates_institution_id"),
        "guide_templates",
        ["institution_id"],
        unique=False,
    )
    op.create_table(
        "guides_folders",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "institution_id", "group_id", "name", name="uq_guides_folder_group_name"
        ),
    )
    op.create_index(
        op.f("ix_guides_folders_group_id"), "guides_folders", ["group_id"], unique=False
    )
    op.create_index(
        op.f("ix_guides_folders_institution_id"),
        "guides_folders",
        ["institution_id"],
        unique=False,
    )
    op.create_table(
        "guides",
        sa.Column("folder_id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=True),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("origin", sa.Enum("ai", "manual", name="guide_origin"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("generating", "draft", "published", "archived", "failed", name="guide_status"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("institution_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(["folder_id"], ["guides_folders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["guide_templates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_guides_folder_id"), "guides", ["folder_id"], unique=False)
    op.create_index(op.f("ix_guides_institution_id"), "guides", ["institution_id"], unique=False)
    op.create_index(op.f("ix_guides_topic_id"), "guides", ["topic_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_guides_topic_id"), table_name="guides")
    op.drop_index(op.f("ix_guides_institution_id"), table_name="guides")
    op.drop_index(op.f("ix_guides_folder_id"), table_name="guides")
    op.drop_table("guides")
    op.drop_index(op.f("ix_guides_folders_institution_id"), table_name="guides_folders")
    op.drop_index(op.f("ix_guides_folders_group_id"), table_name="guides_folders")
    op.drop_table("guides_folders")
    op.drop_index(op.f("ix_guide_templates_institution_id"), table_name="guide_templates")
    op.drop_table("guide_templates")

    # `drop_table` NO borra el tipo nativo que creó el `sa.Enum` del upgrade, así
    # que sin esto un ciclo downgrade→upgrade falla con DuplicateObjectError al
    # reintentar el CREATE TYPE. (La migración 010 deja tipos huérfanos por un
    # motivo distinto e inevitable: ahí lo que se agregó fue un VALOR a un enum
    # existente, y Postgres no permite quitar valores.)
    # `topic_level` NO se toca: lo creó la 002 y `topics.level` sigue usándolo.
    sa.Enum(name="guide_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="guide_origin").drop(op.get_bind(), checkfirst=True)
