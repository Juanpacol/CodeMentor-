"""quita el interruptor por grupo de agentes IA

Revision ID: 026
Revises: 025
Create Date: 2026-07-30 00:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: str | None = "025"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Se quita solo el interruptor on/off por grupo (RF-30): los agentes en sí
    # (AgentName, TASK_TIERS, prompts) siguen intactos y ahora quedan siempre
    # activos — ver `docstring` de `AgentName` en ai/agents/models.py.
    op.drop_table("agent_configs")
    op.execute("DROP TYPE agent_name")


def downgrade() -> None:
    # `sa.Enum(...)` en la columna de abajo crea el tipo `agent_name` en
    # Postgres automáticamente al correr `create_table` — no hace falta un
    # `CREATE TYPE` manual aparte.
    op.create_table(
        "agent_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column(
            "agent_name",
            sa.Enum(
                "progressive_hint",
                "exercise_generation",
                "grading_suggestion",
                "summarize_group",
                "code_integrity",
                "guide_generation",
                name="agent_name",
            ),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("group_id", "agent_name", name="uq_agent_config_group"),
    )
