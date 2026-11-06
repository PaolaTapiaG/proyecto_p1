"""Favorites and user feedback.

Revision ID: 0003_product_surfaces
Revises: 0002_narrative_controls
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003_product_surfaces"
down_revision: str | None = "0002_narrative_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "favoritos_bot",
        sa.Column("id_usuario", sa.String(length=36), nullable=False),
        sa.Column("id_bot", sa.String(length=36), nullable=False),
        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id_usuario"], ["usuarios.id_usuario"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["id_bot"], ["bots.id_bot"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_usuario", "id_bot"),
    )
    op.create_index("ix_favoritos_bot_id_bot", "favoritos_bot", ["id_bot"])

    op.create_table(
        "comentarios_usuario",
        sa.Column("id_comentario", sa.String(length=36), nullable=False),
        sa.Column("id_usuario", sa.String(length=36), nullable=False),
        sa.Column("tipo", sa.String(length=32), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("correo_contacto", sa.String(length=255), nullable=True),
        sa.Column("estado", sa.String(length=32), nullable=False),
        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id_usuario"], ["usuarios.id_usuario"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id_comentario"),
    )
    op.create_index(
        "ix_comentarios_usuario_id_usuario", "comentarios_usuario", ["id_usuario"]
    )
    op.create_index("ix_comentarios_usuario_tipo", "comentarios_usuario", ["tipo"])
    op.create_index("ix_comentarios_usuario_estado", "comentarios_usuario", ["estado"])


def downgrade() -> None:
    op.drop_index("ix_comentarios_usuario_estado", table_name="comentarios_usuario")
    op.drop_index("ix_comentarios_usuario_tipo", table_name="comentarios_usuario")
    op.drop_index("ix_comentarios_usuario_id_usuario", table_name="comentarios_usuario")
    op.drop_table("comentarios_usuario")
    op.drop_index("ix_favoritos_bot_id_bot", table_name="favoritos_bot")
    op.drop_table("favoritos_bot")
