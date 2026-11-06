import re

import httpx
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.db.models import BotMemory
from app.modules.ai.provider import get_embedding_provider


class MemoryService:
    def relevant_memories(
        self,
        db: Session,
        user_id: str,
        bot_id: str,
        conversation_id: str,
        query: str,
        limit: int = 6,
    ) -> list[BotMemory]:
        filters = (
            BotMemory.bot_id == bot_id,
            or_(
                BotMemory.user_id.is_(None),
                and_(
                    BotMemory.user_id == user_id,
                    or_(
                        BotMemory.conversation_id.is_(None),
                        BotMemory.conversation_id == conversation_id,
                    ),
                ),
            ),
        )
        # El canon y los recuerdos elegidos por la persona son compromisos de la historia.
        # Se separan de los turnos recuperados por similitud para no perderlos en escenas largas.
        canonical = list(
            db.scalars(
                select(BotMemory)
                .where(
                    *filters,
                    BotMemory.user_id.is_(None),
                )
                .order_by(BotMemory.importance.desc(), BotMemory.created_at.desc())
                .limit(4)
            )
        )
        manual = list(
            db.scalars(
                select(BotMemory)
                .where(
                    *filters,
                    BotMemory.user_id == user_id,
                    BotMemory.conversation_id == conversation_id,
                    or_(
                        BotMemory.key.like("pinned:%"),
                        BotMemory.key.like("memory:%"),
                    ),
                )
                .order_by(BotMemory.importance.desc(), BotMemory.created_at.desc())
                .limit(6)
            )
        )
        summary = db.scalar(
            select(BotMemory)
            .where(
                *filters,
                BotMemory.user_id == user_id,
                BotMemory.conversation_id == conversation_id,
                BotMemory.key == "auto:summary",
            )
            .order_by(BotMemory.updated_at.desc())
            .limit(1)
        )
        embedding = self._safe_embedding(query)
        is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"
        automatic_filters = (
            *filters,
            BotMemory.user_id == user_id,
            BotMemory.conversation_id == conversation_id,
            or_(BotMemory.key.like("turn:%"), BotMemory.key.like("timeline:%")),
        )
        if embedding is not None and is_postgres:
            statement = (
                select(BotMemory)
                .where(*automatic_filters, BotMemory.embedding.is_not(None))
                .order_by(BotMemory.embedding.cosine_distance(embedding), BotMemory.importance.desc())
                .limit(limit)
            )
        else:
            statement = (
                select(BotMemory)
                .where(*automatic_filters)
                .order_by(BotMemory.created_at.desc())
                .limit(limit)
            )
        automatic = list(db.scalars(statement))
        anchors = [*canonical, *manual, *([summary] if summary else [])]
        seen = {memory.id for memory in anchors}
        return [*anchors, *(memory for memory in automatic if memory.id not in seen)]

    def create_canonical_memory(
        self, db: Session, *, bot_id: str, key: str, value: str, importance: int
    ) -> BotMemory:
        memory = BotMemory(
            bot_id=bot_id,
            key=key,
            value=value,
            importance=importance,
            embedding=self._safe_embedding(f"{key}: {value}"),
        )
        db.add(memory)
        return memory

    def remember_turn(
        self,
        db: Session,
        user_id: str,
        bot_id: str,
        conversation_id: str,
        turn_id: str,
        user_content: str,
        assistant_content: str,
    ) -> None:
        user_state = self._story_excerpt(user_content, limit=680)
        assistant_paragraphs = [
            part.strip()
            for part in re.split(r"\n\s*\n", assistant_content)
            if part.strip()
        ]
        assistant_state = self._story_excerpt(
            " ".join(assistant_paragraphs[-2:]), limit=760
        )
        normalized = (
            f"Accion o situacion del usuario: {user_state}\n"
            f"Consecuencia al cerrar el turno: {assistant_state}"
        )
        if len(normalized) < 60:
            return
        key = f"timeline:{turn_id}"
        memory = db.scalar(
            select(BotMemory).where(
                BotMemory.user_id == user_id,
                BotMemory.conversation_id == conversation_id,
                or_(BotMemory.key == key, BotMemory.key == f"turn:{turn_id}"),
            )
        )
        if memory is None:
            memory = BotMemory(
                user_id=user_id,
                bot_id=bot_id,
                conversation_id=conversation_id,
                key=key,
                importance=2,
            )
            db.add(memory)
        memory.value = normalized
        memory.embedding = self._safe_embedding(normalized)
        self._update_story_summary(
            db,
            user_id=user_id,
            bot_id=bot_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            state=normalized,
        )

    def create_personal_memory(
        self,
        db: Session,
        *,
        user_id: str,
        bot_id: str,
        conversation_id: str,
        key: str,
        value: str,
        category: str = "fact",
        importance: int = 10,
    ) -> BotMemory:
        normalized_category = category.strip().casefold()
        if normalized_category not in {"fact", "relationship", "timeline", "summary"}:
            normalized_category = "fact"
        memory = BotMemory(
            user_id=user_id,
            bot_id=bot_id,
            conversation_id=conversation_id,
            key=f"memory:{normalized_category}:{key.strip()}",
            value=value.strip(),
            embedding=self._safe_embedding(f"{key}: {value}"),
            importance=importance,
        )
        db.add(memory)
        return memory

    @staticmethod
    def clear_automatic_conversation_memories(
        db: Session, *, user_id: str, conversation_id: str
    ) -> None:
        db.execute(
            delete(BotMemory).where(
                BotMemory.user_id == user_id,
                BotMemory.conversation_id == conversation_id,
                ~BotMemory.key.like("pinned:%"),
                ~BotMemory.key.like("memory:%"),
            )
        )

    def _update_story_summary(
        self,
        db: Session,
        *,
        user_id: str,
        bot_id: str,
        conversation_id: str,
        turn_id: str,
        state: str,
    ) -> None:
        summary = db.scalar(
            select(BotMemory).where(
                BotMemory.user_id == user_id,
                BotMemory.conversation_id == conversation_id,
                BotMemory.key == "auto:summary",
            )
        )
        entry = f"Turno {turn_id[:8]}: {self._story_excerpt(state, limit=520)}"
        previous = summary.value if summary else ""
        value = self._story_excerpt(f"{previous}\n{entry}".strip(), limit=2200)
        if summary is None:
            summary = BotMemory(
                user_id=user_id,
                bot_id=bot_id,
                conversation_id=conversation_id,
                key="auto:summary",
                importance=9,
            )
            db.add(summary)
        summary.value = value
        summary.embedding = self._safe_embedding(value)

    @staticmethod
    def category_for(memory: BotMemory) -> str:
        key = memory.key
        if memory.user_id is None:
            return "canon"
        if key.startswith("memory:"):
            return key.split(":", 2)[1]
        if key.startswith("timeline:") or key.startswith("turn:"):
            return "timeline"
        if key == "auto:summary":
            return "summary"
        return "fact"

    @classmethod
    def display_key(cls, memory: BotMemory) -> str:
        if memory.key.startswith("memory:"):
            return memory.key.split(":", 2)[-1]
        if memory.key.startswith("pinned:"):
            return memory.key.removeprefix("pinned:")
        if cls.category_for(memory) == "summary":
            return "Resumen acumulado"
        if cls.category_for(memory) == "timeline":
            return "Linea temporal"
        return memory.key.removeprefix("canon:")

    @staticmethod
    def _safe_embedding(text: str) -> list[float] | None:
        provider = get_embedding_provider()
        if provider is None:
            return None
        try:
            return provider.embed(text)
        except (RuntimeError, httpx.HTTPError):
            return None

    @staticmethod
    def _story_excerpt(text: str, *, limit: int) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= limit:
            return compact
        ending = compact[-(limit // 3) :].lstrip()
        opening = compact[: limit - len(ending) - 5].rsplit(" ", 1)[0]
        return f"{opening} […] {ending}"


memory_service = MemoryService()
