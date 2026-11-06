"""Initial PostgreSQL and pgvector schema for Lumora.

Revision ID: 0001_initial
Revises:
"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    json_type = postgresql.JSONB() if is_postgres else sa.JSON()
    embedding_type = Vector(1024) if is_postgres else sa.JSON()
    json_default = sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'")

    op.create_table(
        "usuarios",
        sa.Column("id_usuario", sa.String(36), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("correo", sa.String(255), nullable=False, unique=True),
        sa.Column("contrasena_hash", sa.String(255)),
        sa.Column("foto_perfil", sa.String(500)),
        sa.Column("fecha_registro", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("estado", sa.String(32), nullable=False, server_default="active"),
        sa.Column("supabase_user_id", sa.String(128), unique=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_usuarios_correo", "usuarios", ["correo"], unique=True)
    op.create_index("ix_usuarios_supabase_user_id", "usuarios", ["supabase_user_id"], unique=True)

    op.create_table(
        "personas_usuario",
        sa.Column("id_persona", sa.String(36), primary_key=True),
        sa.Column(
            "id_usuario",
            sa.String(36),
            sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("expresion_genero", sa.String(80)),
        sa.Column("personalidad", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text()),
        sa.Column("avatar", sa.String(500)),
        sa.Column("estado", sa.String(32), nullable=False, server_default="active"),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_personas_usuario_id_usuario", "personas_usuario", ["id_usuario"])

    op.create_table(
        "bots",
        sa.Column("id_bot", sa.String(36), primary_key=True),
        sa.Column(
            "id_creador",
            sa.String(36),
            sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("apellido", sa.String(120)),
        sa.Column("personalidad", sa.Text(), nullable=False),
        sa.Column("detalles", json_type, nullable=False, server_default=json_default),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("escenario", sa.Text()),
        sa.Column("saludo_inicial", sa.Text()),
        sa.Column("avatar", sa.String(500)),
        sa.Column("modelo_ia", sa.String(120), nullable=False, server_default="qwen3:8b"),
        sa.Column("visibilidad", sa.String(32), nullable=False, server_default="private"),
        sa.Column("total_chats", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bots_id_creador", "bots", ["id_creador"])
    op.create_index("ix_bots_visibilidad", "bots", ["visibilidad"])

    op.create_table(
        "conversaciones",
        sa.Column("id_conversacion", sa.String(36), primary_key=True),
        sa.Column(
            "id_usuario",
            sa.String(36),
            sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "id_bot",
            sa.String(36),
            sa.ForeignKey("bots.id_bot", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "id_persona_usuario",
            sa.String(36),
            sa.ForeignKey("personas_usuario.id_persona", ondelete="SET NULL"),
        ),
        sa.Column("titulo", sa.String(180), nullable=False),
        sa.Column("estado", sa.String(32), nullable=False, server_default="active"),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ultima_actividad", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversaciones_id_usuario", "conversaciones", ["id_usuario"])
    op.create_index("ix_conversaciones_id_bot", "conversaciones", ["id_bot"])
    op.create_index(
        "ix_conversaciones_id_persona_usuario", "conversaciones", ["id_persona_usuario"]
    )

    op.create_table(
        "mensajes",
        sa.Column("id_mensaje", sa.String(36), primary_key=True),
        sa.Column(
            "id_conversacion",
            sa.String(36),
            sa.ForeignKey("conversaciones.id_conversacion", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("remitente", sa.String(32), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estado_moderacion", sa.String(32), nullable=False, server_default="allowed"),
        sa.Column("metadatos", json_type, nullable=False, server_default=json_default),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mensajes_id_conversacion", "mensajes", ["id_conversacion"])

    op.create_table(
        "memorias_bot",
        sa.Column("id_memoria", sa.String(36), primary_key=True),
        sa.Column(
            "id_bot",
            sa.String(36),
            sa.ForeignKey("bots.id_bot", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "id_usuario",
            sa.String(36),
            sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        ),
        sa.Column(
            "id_conversacion",
            sa.String(36),
            sa.ForeignKey("conversaciones.id_conversacion", ondelete="CASCADE"),
        ),
        sa.Column("clave", sa.String(160), nullable=False),
        sa.Column("valor", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type),
        sa.Column("importancia", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_memorias_bot_id_bot", "memorias_bot", ["id_bot"])
    op.create_index("ix_memorias_bot_id_usuario", "memorias_bot", ["id_usuario"])
    if is_postgres:
        op.execute(
            "CREATE INDEX ix_memorias_bot_embedding_hnsw ON memorias_bot "
            "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
        )

    op.create_table(
        "moderation_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("usuarios.id_usuario", ondelete="SET NULL")),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversaciones.id_conversacion", ondelete="SET NULL"),
        ),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )

    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversaciones.id_conversacion", ondelete="SET NULL"),
        ),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_micros", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
    )
    op.create_index("ix_usage_records_user_id", "usage_records", ["user_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("plan", sa.String(80), nullable=False, server_default="free"),
        sa.Column("status", sa.String(80), nullable=False, server_default="active"),
        sa.Column("provider_customer_id", sa.String(180)),
        sa.Column("provider_subscription_id", sa.String(180)),
        *_timestamps(),
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "admin_user_id",
            sa.String(36),
            sa.ForeignKey("usuarios.id_usuario", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(120), nullable=False),
        sa.Column("target_id", sa.String(120)),
        sa.Column("metadata_json", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )


def downgrade() -> None:
    for table in (
        "admin_audit_logs",
        "subscriptions",
        "usage_records",
        "moderation_events",
        "memorias_bot",
        "mensajes",
        "conversaciones",
        "bots",
        "personas_usuario",
        "usuarios",
    ):
        op.drop_table(table)
