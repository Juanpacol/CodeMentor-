"""agente de guías: valor 'guide_writer' en el enum agent_name

Revision ID: 016
Revises: 015
Create Date: 2026-07-26 12:45:11.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Fase 16: nuevo valor del enum nativo `agent_name` — alembic autogenerate
    # NO detecta cambios de VALORES de un enum existente (solo tablas/columnas
    # nuevas), así que este ALTER TYPE va a mano, igual que la migración 010.
    # SQLAlchemy persiste el *nombre* del miembro de Python ("guide_writer"), no
    # su `.value` ("guide_generation") — ver el comentario de la 010, verificado
    # con `enum_range` contra los valores ya existentes.
    # Va en su propia migración (y no dentro de la 015) porque Postgres solo
    # permite ADD VALUE en transacción si el valor no se USA en esa misma
    # transacción, y separarlas deja esa restricción imposible de violar por
    # accidente cuando alguien agregue un backfill acá.
    op.execute("ALTER TYPE agent_name ADD VALUE IF NOT EXISTS 'guide_writer'")


def downgrade() -> None:
    # Postgres no permite quitar un valor de un enum, así que 'guide_writer' se
    # queda en `agent_name` tras un downgrade — inofensivo: si esta migración se
    # revierte, ninguna fila de `agent_configs` lo referencia (el agente no
    # existe sin el resto de la Fase 16). Mismo razonamiento que la 010.
    pass
