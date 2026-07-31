"""estados `cancelled` en corridas de rúbrica, sus ítems y las guías

Revision ID: 022
Revises: 021
Create Date: 2026-07-28 00:14:09.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "022"
down_revision: str | None = "021"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Cancelar dejaba la corrida en `failed`, indistinguible de un fallo real, y
    # a las guías atascadas en `generating` sin ninguna salida. Los tres enums
    # nativos necesitan el valor nuevo — alembic autogenerate NO detecta cambios
    # de VALORES de un enum existente (solo tablas/columnas nuevas), así que van
    # a mano, igual que las migraciones 010 y 016.
    #
    # Postgres solo permite ADD VALUE dentro de una transacción si el valor no se
    # USA en esa misma transacción: por eso acá no hay backfill de filas.
    op.execute("ALTER TYPE rubric_run_status ADD VALUE IF NOT EXISTS 'cancelled'")
    op.execute("ALTER TYPE rubric_item_status ADD VALUE IF NOT EXISTS 'cancelled'")
    op.execute("ALTER TYPE guide_status ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # Postgres no permite quitar un valor de un enum. Los tres 'cancelled' se
    # quedan tras un downgrade — inofensivo mientras ninguna fila los use, y si
    # alguna los usa, borrarlos rompería más de lo que arreglaría. Mismo
    # razonamiento que las migraciones 010 y 016.
    pass
