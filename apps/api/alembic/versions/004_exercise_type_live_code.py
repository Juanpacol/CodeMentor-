"""agregar tipo ejercicio live_code

Revision ID: 004
Revises: 003
Create Date: 2026-07-16 18:39:39.659467

"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # RE-05 showcase (§4.2 "reto de código en vivo"): adding an 8th exercise
    # type is a data change (new enum value), not a rewrite of the grading
    # engine — see modules/grading/live_code.py.
    op.execute("ALTER TYPE exercise_type ADD VALUE IF NOT EXISTS 'live_code'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; downgrading this cleanly would
    # require rebuilding the type, which is out of scope for a demo project.
    pass
