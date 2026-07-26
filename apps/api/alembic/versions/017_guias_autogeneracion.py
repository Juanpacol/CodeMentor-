"""guías: opt-in de autogeneración por carpeta

Revision ID: 017
Revises: 016
Create Date: 2026-07-26 13:10:04.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Nullable sin default: NULL significa "esta carpeta no se autogenera", que es
    # lo correcto para las carpetas que ya existen — la automatización nunca se
    # activa sola sobre contenido que un docente ya venía manejando a mano.
    op.add_column(
        "guides_folders",
        sa.Column("auto_generate_template_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_guides_folders_auto_generate_template_id",
        "guides_folders",
        "guide_templates",
        ["auto_generate_template_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_guides_folders_auto_generate_template_id", "guides_folders", type_="foreignkey"
    )
    op.drop_column("guides_folders", "auto_generate_template_id")
