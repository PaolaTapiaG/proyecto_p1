"""Adult confirmation and per-conversation mature content control.

Revision ID: 0004_mature_content_controls
Revises: 0003_product_surfaces
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_mature_content_controls"
down_revision: str | None = "0003_product_surfaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column(
            "mayoria_edad_confirmada",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "conversaciones",
        sa.Column(
            "contenido_adulto_habilitado",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("conversaciones", "contenido_adulto_habilitado")
    op.drop_column("usuarios", "mayoria_edad_confirmada")
