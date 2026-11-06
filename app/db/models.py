import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


EMBEDDING_DIMENSIONS = 1024
JsonType = JSONB().with_variant(JSON(), "sqlite")
VectorType = Vector(EMBEDDING_DIMENSIONS).with_variant(JSON(), "sqlite")


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column("id_usuario", String(36), primary_key=True, default=new_uuid)
    display_name: Mapped[str] = mapped_column("nombre", String(120), nullable=False)
    email: Mapped[str] = mapped_column("correo", String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column("contrasena_hash", String(255))
    avatar_path: Mapped[str | None] = mapped_column("foto_perfil", String(500))
    created_at: Mapped[datetime] = mapped_column(
        "fecha_registro", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        "fecha_actualizacion",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column("estado", String(32), default="active", index=True)
    supabase_user_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    adult_confirmed: Mapped[bool] = mapped_column(
        "mayoria_edad_confirmada", Boolean, default=False, nullable=False
    )


class UserPersona(Base):
    __tablename__ = "personas_usuario"

    id: Mapped[str] = mapped_column("id_persona", String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        "id_usuario", ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column("nombre", String(120), nullable=False)
    gender_expression: Mapped[str | None] = mapped_column("expresion_genero", String(80))
    personality: Mapped[str] = mapped_column("personalidad", Text, nullable=False)
    description: Mapped[str | None] = mapped_column("descripcion", Text)
    avatar_path: Mapped[str | None] = mapped_column("avatar", String(500))
    status: Mapped[str] = mapped_column("estado", String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        "fecha_actualizacion",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserFollow(Base):
    __tablename__ = "seguimientos_usuario"

    follower_id: Mapped[str] = mapped_column(
        "id_seguidor",
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        primary_key=True,
    )
    author_id: Mapped[str] = mapped_column(
        "id_autor",
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Character(Base):
    """Bot de roleplay. El nombre Python se conserva para compatibilidad interna."""

    __tablename__ = "bots"

    id: Mapped[str] = mapped_column("id_bot", String(36), primary_key=True, default=new_uuid)
    owner_id: Mapped[str] = mapped_column(
        "id_creador", ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column("nombre", String(120), index=True)
    last_name: Mapped[str | None] = mapped_column("apellido", String(120))
    persona: Mapped[str] = mapped_column("personalidad", Text)
    details_json: Mapped[dict] = mapped_column("detalles", JsonType, default=dict)
    description: Mapped[str] = mapped_column("descripcion", Text)
    scenario: Mapped[str | None] = mapped_column("escenario", Text)
    greeting: Mapped[str | None] = mapped_column("saludo_inicial", Text)
    avatar_path: Mapped[str | None] = mapped_column("avatar", String(500))
    ai_model: Mapped[str] = mapped_column("modelo_ia", String(120), default="qwen3:8b")
    source_name: Mapped[str | None] = mapped_column("obra_origen", String(180))
    source_type: Mapped[str] = mapped_column("tipo_origen", String(60), default="original")
    research_enabled: Mapped[bool] = mapped_column(
        "investigacion_habilitada", Boolean, default=False, nullable=False
    )
    research_summary: Mapped[str | None] = mapped_column("resumen_investigacion", Text)
    research_url: Mapped[str | None] = mapped_column("url_investigacion", String(500))
    research_updated_at: Mapped[datetime | None] = mapped_column(
        "fecha_investigacion", DateTime(timezone=True)
    )
    visibility: Mapped[str] = mapped_column("visibilidad", String(32), default="private", index=True)
    total_chats: Mapped[int] = mapped_column("total_chats", Integer, default=0)
    total_likes: Mapped[int] = mapped_column("total_likes", Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        "fecha_actualizacion",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Conversation(Base):
    __tablename__ = "conversaciones"

    id: Mapped[str] = mapped_column(
        "id_conversacion", String(36), primary_key=True, default=new_uuid
    )
    user_id: Mapped[str] = mapped_column(
        "id_usuario", ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), index=True
    )
    character_id: Mapped[str] = mapped_column(
        "id_bot", ForeignKey("bots.id_bot", ondelete="RESTRICT"), index=True
    )
    user_persona_id: Mapped[str | None] = mapped_column(
        "id_persona_usuario",
        ForeignKey("personas_usuario.id_persona", ondelete="SET NULL"),
        index=True,
    )
    title: Mapped[str] = mapped_column("titulo", String(180))
    creative_mode: Mapped[bool] = mapped_column(
        "modo_creativo", Boolean, default=True, nullable=False
    )
    auto_roleplay_user: Mapped[bool] = mapped_column(
        "interpretar_usuario", Boolean, default=False, nullable=False
    )
    story_preferences: Mapped[str | None] = mapped_column("preferencias_historia", Text)
    minimum_paragraphs: Mapped[int] = mapped_column(
        "parrafos_minimos", Integer, default=8, nullable=False
    )
    mature_content_enabled: Mapped[bool] = mapped_column(
        "contenido_adulto_habilitado", Boolean, default=False, nullable=False
    )
    status: Mapped[str] = mapped_column("estado", String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        "ultima_actividad",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Message(Base):
    __tablename__ = "mensajes"

    id: Mapped[str] = mapped_column("id_mensaje", String(36), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(
        "id_conversacion",
        ForeignKey("conversaciones.id_conversacion", ondelete="CASCADE"),
        index=True,
    )
    sender: Mapped[str] = mapped_column("remitente", String(32), index=True)
    content: Mapped[str] = mapped_column("contenido", Text)
    reply_to_message_id: Mapped[str | None] = mapped_column(
        "respuesta_a",
        ForeignKey("mensajes.id_mensaje", ondelete="CASCADE"),
        index=True,
    )
    alternative_index: Mapped[int] = mapped_column(
        "indice_alternativa", Integer, default=1, nullable=False
    )
    is_selected: Mapped[bool] = mapped_column(
        "seleccionado", Boolean, default=True, nullable=False, index=True
    )
    token_count: Mapped[int] = mapped_column("total_tokens", Integer, default=0)
    moderation_status: Mapped[str] = mapped_column(
        "estado_moderacion", String(32), default="allowed"
    )
    metadata_json: Mapped[dict] = mapped_column("metadatos", JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        "fecha_actualizacion",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BotMemory(Base):
    __tablename__ = "memorias_bot"

    id: Mapped[str] = mapped_column("id_memoria", String(36), primary_key=True, default=new_uuid)
    bot_id: Mapped[str] = mapped_column(
        "id_bot", ForeignKey("bots.id_bot", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        "id_usuario", ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        "id_conversacion",
        ForeignKey("conversaciones.id_conversacion", ondelete="CASCADE"),
        index=True,
    )
    key: Mapped[str] = mapped_column("clave", String(160), index=True)
    value: Mapped[str] = mapped_column("valor", Text)
    embedding: Mapped[list[float] | None] = mapped_column(VectorType, nullable=True)
    importance: Mapped[int] = mapped_column("importancia", Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        "fecha_actualizacion",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BotFavorite(Base):
    __tablename__ = "favoritos_bot"

    user_id: Mapped[str] = mapped_column(
        "id_usuario",
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        primary_key=True,
    )
    bot_id: Mapped[str] = mapped_column(
        "id_bot",
        ForeignKey("bots.id_bot", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserFeedback(Base):
    __tablename__ = "comentarios_usuario"

    id: Mapped[str] = mapped_column("id_comentario", String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        "id_usuario", ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column("tipo", String(32), index=True)
    message: Mapped[str] = mapped_column("mensaje", Text)
    contact_email: Mapped[str | None] = mapped_column("correo_contacto", String(255))
    status: Mapped[str] = mapped_column("estado", String(32), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(
        "fecha_creacion", DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        "fecha_actualizacion",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ModerationEvent(Base):
    __tablename__ = "moderation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversaciones.id_conversacion", ondelete="SET NULL"), index=True
    )
    category: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversaciones.id_conversacion", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_micros: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_subscriptions_user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), index=True
    )
    plan: Mapped[str] = mapped_column(String(80), default="local")
    status: Mapped[str] = mapped_column(String(80), default="active")
    provider_customer_id: Mapped[str | None] = mapped_column(String(180), index=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(180), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_user_id: Mapped[str] = mapped_column(
        ForeignKey("usuarios.id_usuario", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str] = mapped_column(String(120))
    target_id: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# Alias temporal para imports anteriores mientras la API migra a la terminologia Bot.
MemoryEntry = BotMemory
