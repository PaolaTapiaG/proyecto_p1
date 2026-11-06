"""Add author follows for discovery profiles.

Revision ID: 0006_author_follows
Revises: 0005_local_access
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_author_follows"
down_revision = "0005_local_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seguimientos_usuario",
        sa.Column(
            "id_seguidor",
            sa.String(36),
            sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "id_autor",
            sa.String(36),
            sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_seguimientos_usuario_id_autor", "seguimientos_usuario", ["id_autor"])


def downgrade() -> None:
    op.drop_index("ix_seguimientos_usuario_id_autor", table_name="seguimientos_usuario")
    op.drop_table("seguimientos_usuario")
