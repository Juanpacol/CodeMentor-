"""quita el tipo de ejercicio order_lines

Revision ID: 024
Revises: 023
Create Date: 2026-07-30 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "024"
down_revision: str | None = "877d0f5d3ae7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_OLD_VALUES = (
    "true_false",
    "multiple_choice",
    "fill_code",
    "find_error",
    "trace_variables",
    "order_lines",
    "argued_response",
    "live_code",
)
_NEW_VALUES = (
    "true_false",
    "multiple_choice",
    "fill_code",
    "find_error",
    "trace_variables",
    "argued_response",
    "live_code",
)


def upgrade() -> None:
    # Postgres no permite DROP VALUE de un enum, así que hay que recrear el
    # tipo. La tabla `exercises` está vacía en producción a la fecha de esta
    # migración, así que no hace falta backfill de filas con `order_lines`.
    op.execute("ALTER TYPE exercise_type RENAME TO exercise_type_old")
    new_values = ", ".join(f"'{v}'" for v in _NEW_VALUES)
    op.execute(f"CREATE TYPE exercise_type AS ENUM ({new_values})")
    op.execute(
        "ALTER TABLE exercises ALTER COLUMN type TYPE exercise_type "
        "USING type::text::exercise_type"
    )
    op.execute("DROP TYPE exercise_type_old")


def downgrade() -> None:
    op.execute("ALTER TYPE exercise_type RENAME TO exercise_type_old")
    old_values = ", ".join(f"'{v}'" for v in _OLD_VALUES)
    op.execute(f"CREATE TYPE exercise_type AS ENUM ({old_values})")
    op.execute(
        "ALTER TABLE exercises ALTER COLUMN type TYPE exercise_type "
        "USING type::text::exercise_type"
    )
    op.execute("DROP TYPE exercise_type_old")
