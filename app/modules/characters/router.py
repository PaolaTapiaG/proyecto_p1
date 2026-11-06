import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db.models import BotFavorite, BotMemory, Character, User
from app.db.session import get_db
from app.modules.characters.schemas import (
    BotMemoryCreate,
    BotMemoryRead,
    BotAssistRead,
    BotAssistRequest,
    CharacterCreate,
    CharacterRead,
)
from app.modules.ai.provider import AIMessage, GenerationOptions, get_ai_provider
from app.modules.memory.service import memory_service
from app.modules.research.service import research_service


router = APIRouter(tags=["Bots"])


def visible_bot(db: Session, user: User, bot_id: str) -> Character:
    bot = db.get(Character, bot_id)
    if not bot or (bot.owner_id != user.id and bot.visibility != "public"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot not found")
    return bot


@router.post("", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
def create_character(
    payload: CharacterCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Character:
    bot = Character(owner_id=user.id, **payload.model_dump())
    if bot.research_enabled:
        try:
            full_name = " ".join(value for value in (bot.name, bot.last_name) if value)
            research = research_service.research(full_name, bot.source_name)
        except httpx.HTTPError:
            research = None
        if research:
            bot.research_summary = research.summary
            bot.research_url = research.url
            bot.research_updated_at = research.researched_at
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


@router.get("", response_model=list[CharacterRead])
def list_characters(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Character]:
    statement = (
        select(Character)
        .where(or_(Character.owner_id == user.id, Character.visibility == "public"))
        .order_by(Character.total_chats.desc(), Character.created_at.desc())
    )
    return list(db.scalars(statement))


@router.get("/favorites", response_model=list[CharacterRead])
def list_favorites(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Character]:
    statement = (
        select(Character)
        .join(BotFavorite, BotFavorite.bot_id == Character.id)
        .where(BotFavorite.user_id == user.id)
        .order_by(BotFavorite.created_at.desc())
    )
    return list(db.scalars(statement))


@router.get("/search", response_model=list[CharacterRead])
def search_characters(
    q: str,
    limit: int = 24,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Character]:
    query = q.strip()
    if len(query) < 2:
        return []
    safe_limit = min(max(limit, 1), 48)
    pattern = f"%{query}%"
    statement = (
        select(Character)
        .where(
            or_(Character.owner_id == user.id, Character.visibility == "public"),
            or_(
                Character.name.ilike(pattern),
                Character.last_name.ilike(pattern),
                Character.description.ilike(pattern),
                Character.source_name.ilike(pattern),
            ),
        )
        .order_by(Character.total_likes.desc(), Character.total_chats.desc())
        .limit(safe_limit)
    )
    return list(db.scalars(statement))


@router.post("/assist", response_model=BotAssistRead)
def assist_character_creation(
    payload: BotAssistRequest,
    _: User = Depends(current_user),
) -> BotAssistRead:
    labels = {
        "greeting": "un saludo inicial que abra una escena y facilite responder",
        "persona": "una personalidad clara con voz, valores, defectos y limites",
        "description": "una descripcion breve y atractiva del personaje",
        "scenario": "un escenario base flexible para iniciar historias",
    }
    prompt = [
        AIMessage(
            role="system",
            content=(
                "Eres asistente de creacion de personajes de roleplay. Escribe en espanol, "
                "respeta las notas y devuelve solo el texto listo para pegar, sin encabezados ni "
                "explicaciones. No inventes canon incompatible con la obra indicada."
            ),
        ),
        AIMessage(
            role="user",
            content=(
                f"Personaje: {payload.name}. Obra: {payload.source_name or 'original'}. "
                f"Necesito {labels[payload.field]}. Notas: {payload.notes}"
            ),
        ),
    ]
    try:
        response = get_ai_provider().complete(
            prompt,
            options=GenerationOptions(
                temperature=0.65,
                top_p=0.8,
                top_k=20,
                repeat_penalty=1.1,
                max_tokens=500,
                think=True,
            ),
        )
    except (RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI assistant failed") from exc
    return BotAssistRead(field=payload.field, suggestion=response.content)


@router.get("/{bot_id}", response_model=CharacterRead)
def get_character(
    bot_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Character:
    return visible_bot(db, user, bot_id)


@router.post("/{bot_id}/favorite", status_code=status.HTTP_201_CREATED)
def favorite_character(
    bot_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    bot = visible_bot(db, user, bot_id)
    favorite = db.get(BotFavorite, (user.id, bot.id))
    if not favorite:
        db.add(BotFavorite(user_id=user.id, bot_id=bot.id))
        bot.total_likes += 1
        db.commit()
    return {"bot_id": bot.id, "favorite": True, "total_likes": bot.total_likes}


@router.delete("/{bot_id}/favorite")
def unfavorite_character(
    bot_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    bot = visible_bot(db, user, bot_id)
    favorite = db.get(BotFavorite, (user.id, bot.id))
    if favorite:
        db.delete(favorite)
        bot.total_likes = max(0, bot.total_likes - 1)
        db.commit()
    return {"bot_id": bot.id, "favorite": False, "total_likes": bot.total_likes}


@router.post("/{bot_id}/research", response_model=CharacterRead)
def refresh_character_research(
    bot_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Character:
    bot = visible_bot(db, user, bot_id)
    if bot.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the bot author can research it")
    if not bot.research_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Character research is disabled")
    try:
        full_name = " ".join(value for value in (bot.name, bot.last_name) if value)
        research = research_service.research(full_name, bot.source_name)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Research provider failed") from exc
    if not research:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No canonical reference was found")
    bot.research_summary = research.summary
    bot.research_url = research.url
    bot.research_updated_at = research.researched_at
    db.commit()
    db.refresh(bot)
    return bot


@router.post(
    "/{bot_id}/memories",
    response_model=BotMemoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_bot_memory(
    bot_id: str,
    payload: BotMemoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> BotMemory:
    bot = visible_bot(db, user, bot_id)
    if bot.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the bot author can edit memory")
    memory = memory_service.create_canonical_memory(
        db, bot_id=bot.id, key=payload.key, value=payload.value, importance=payload.importance
    )
    db.commit()
    db.refresh(memory)
    return memory


@router.get("/{bot_id}/memories", response_model=list[BotMemoryRead])
def list_bot_memories(
    bot_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[BotMemory]:
    bot = visible_bot(db, user, bot_id)
    if bot.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the bot author can inspect memory")
    statement = (
        select(BotMemory)
        .where(BotMemory.bot_id == bot.id, BotMemory.user_id.is_(None))
        .order_by(BotMemory.importance.desc(), BotMemory.created_at.desc())
    )
    return list(db.scalars(statement))
