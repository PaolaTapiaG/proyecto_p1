"""Narrative controls, canonical research and response alternatives.

Revision ID: 0002_narrative_controls
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_narrative_controls"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bots") as batch:
        batch.add_column(sa.Column("obra_origen", sa.String(180)))
        batch.add_column(
            sa.Column("tipo_origen", sa.String(60), nullable=False, server_default="original")
        )
        batch.add_column(
            sa.Column(
                "investigacion_habilitada",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("resumen_investigacion", sa.Text()))
        batch.add_column(sa.Column("url_investigacion", sa.String(500)))
        batch.add_column(sa.Column("fecha_investigacion", sa.DateTime(timezone=True)))

    with op.batch_alter_table("conversaciones") as batch:
        batch.add_column(
            sa.Column("modo_creativo", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(
            sa.Column(
                "interpretar_usuario", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch.add_column(sa.Column("preferencias_historia", sa.Text()))
        batch.add_column(
            sa.Column("parrafos_minimos", sa.Integer(), nullable=False, server_default="8")
        )

    with op.batch_alter_table("mensajes") as batch:
        batch.add_column(sa.Column("respuesta_a", sa.String(36)))
        batch.add_column(
            sa.Column("indice_alternativa", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(
            sa.Column("seleccionado", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.create_foreign_key(
            "fk_mensajes_respuesta_a",
            "mensajes",
            ["respuesta_a"],
            ["id_mensaje"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_mensajes_respuesta_a", ["respuesta_a"])
        batch.create_index("ix_mensajes_seleccionado", ["seleccionado"])


def downgrade() -> None:
    with op.batch_alter_table("mensajes") as batch:
        batch.drop_index("ix_mensajes_seleccionado")
        batch.drop_index("ix_mensajes_respuesta_a")
        batch.drop_constraint("fk_mensajes_respuesta_a", type_="foreignkey")
        batch.drop_column("seleccionado")
        batch.drop_column("indice_alternativa")
        batch.drop_column("respuesta_a")

    with op.batch_alter_table("conversaciones") as batch:
        batch.drop_column("parrafos_minimos")
        batch.drop_column("preferencias_historia")
        batch.drop_column("interpretar_usuario")
        batch.drop_column("modo_creativo")

    with op.batch_alter_table("bots") as batch:
        batch.drop_column("fecha_investigacion")
        batch.drop_column("url_investigacion")
        batch.drop_column("resumen_investigacion")
        batch.drop_column("investigacion_habilitada")
        batch.drop_column("tipo_origen")
        batch.drop_column("obra_origen")
