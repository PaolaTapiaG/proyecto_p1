from collections.abc import Generator
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.core.redis import LockBusy, redis_gateway
from app.db.models import BotMemory, Character, Conversation, Message, User, UserPersona
from app.db.session import get_db
from app.modules.conversations.orchestrator import (
    AlternativeLimitReached,
    roleplay_orchestrator,
)
from app.modules.conversations.schemas import (
    ConversationCreate,
    ConversationMemoryCreate,
    ConversationMemoryRead,
    ConversationRead,
    ConversationSettingsUpdate,
    MessageRead,
    MessageRegenerate,
    MessageSend,
    RewindRead,
    SuggestedReplyRead,
)
from app.modules.memory.service import memory_service


router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _visible_character(db: Session, user: User, character_id: str) -> Character:
    character = db.get(Character, character_id)
    if not character or (character.owner_id != user.id and character.visibility != "public"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    return character


def _owned_conversation(db: Session, user: User, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def start_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Conversation:
    character = _visible_character(db, user, payload.character_id)
    if payload.mature_content_enabled and not user.adult_confirmed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Confirma que tienes 18 años o más antes de activar el modo +18",
        )
    if payload.user_persona_id:
        user_persona = db.get(UserPersona, payload.user_persona_id)
        if not user_persona or user_persona.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Persona not found")
    conversation = Conversation(
        user_id=user.id,
        character_id=character.id,
        user_persona_id=payload.user_persona_id,
        title=payload.title or f"Chat with {character.name}",
        creative_mode=payload.creative_mode,
        auto_roleplay_user=payload.auto_roleplay_user,
        story_preferences=payload.story_preferences,
        minimum_paragraphs=payload.minimum_paragraphs,
        mature_content_enabled=payload.mature_content_enabled,
    )
    character.total_chats += 1
    db.add(conversation)
    db.flush()
    if character.greeting:
        db.add(
            Message(
                conversation_id=conversation.id,
                sender="assistant",
                content=character.greeting,
            )
        )
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Conversation]:
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(db.scalars(statement))


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Conversation:
    return _owned_conversation(db, user, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationRead)
def update_conversation_settings(
    conversation_id: str,
    payload: ConversationSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Conversation:
    conversation = _owned_conversation(db, user, conversation_id)
    if payload.mature_content_enabled is True and not user.adult_confirmed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Confirma que tienes 18 años o más antes de activar el modo +18",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(conversation, field, value)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get(
    "/{conversation_id}/memories", response_model=list[ConversationMemoryRead]
)
def list_conversation_memories(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[BotMemory]:
    conversation = _owned_conversation(db, user, conversation_id)
    statement = (
        select(BotMemory)
        .where(
            BotMemory.user_id == user.id,
            BotMemory.conversation_id == conversation.id,
            BotMemory.importance >= 5,
        )
        .order_by(BotMemory.importance.desc(), BotMemory.created_at.desc())
    )
    return list(db.scalars(statement))


@router.post(
    "/{conversation_id}/memories",
    response_model=ConversationMemoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_memory(
    conversation_id: str,
    payload: ConversationMemoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> BotMemory:
    conversation = _owned_conversation(db, user, conversation_id)
    memory = memory_service.create_personal_memory(
        db,
        user_id=user.id,
        bot_id=conversation.character_id,
        conversation_id=conversation.id,
        key=payload.key,
        value=payload.value,
        category=payload.category,
        importance=payload.importance,
    )
    db.commit()
    db.refresh(memory)
    return memory


@router.delete("/{conversation_id}/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_memory(
    conversation_id: str,
    memory_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    conversation = _owned_conversation(db, user, conversation_id)
    memory = db.get(BotMemory, memory_id)
    if (
        not memory
        or memory.user_id != user.id
        or memory.conversation_id != conversation.id
        or memory.importance < 5
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
    db.delete(memory)
    db.commit()


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(
    conversation_id: str,
    include_alternatives: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Message]:
    conversation = _owned_conversation(db, user, conversation_id)
    conditions = [Message.conversation_id == conversation.id]
    if not include_alternatives:
        conditions.append(
            or_(Message.sender != "assistant", Message.is_selected.is_(True))
        )
    statement = select(Message).where(*conditions).order_by(
        Message.created_at.asc(), Message.id.asc()
    )
    return list(db.scalars(statement))


@router.post("/{conversation_id}/messages", response_model=MessageRead)
def send_message(
    conversation_id: str,
    payload: MessageSend,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = _owned_conversation(db, user, conversation_id)
    if payload.stream:
        return StreamingResponse(
            _locked_event_stream(db, conversation, payload.content),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        with redis_gateway.conversation_lock(conversation.id):
            return roleplay_orchestrator.send_message(db, conversation, payload.content)
    except LockBusy as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except (RuntimeError, httpx.HTTPError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI provider failed") from exc


def _assistant_message(
    db: Session, conversation: Conversation, message_id: str
) -> Message:
    message = db.get(Message, message_id)
    if (
        not message
        or message.conversation_id != conversation.id
        or message.sender != "assistant"
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assistant message not found")
    return message


@router.get(
    "/{conversation_id}/messages/{message_id}/alternatives",
    response_model=list[MessageRead],
)
def list_alternatives(
    conversation_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Message]:
    conversation = _owned_conversation(db, user, conversation_id)
    message = _assistant_message(db, conversation, message_id)
    if not message.reply_to_message_id:
        return [message]
    statement = (
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.sender == "assistant",
            Message.reply_to_message_id == message.reply_to_message_id,
        )
        .order_by(Message.alternative_index.asc())
    )
    return list(db.scalars(statement))


@router.put(
    "/{conversation_id}/messages/{message_id}/select",
    response_model=MessageRead,
)
def select_alternative(
    conversation_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Message:
    conversation = _owned_conversation(db, user, conversation_id)
    message = _assistant_message(db, conversation, message_id)
    if not message.reply_to_message_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This message has no alternatives")
    alternatives = db.scalars(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.sender == "assistant",
            Message.reply_to_message_id == message.reply_to_message_id,
        )
    )
    for item in alternatives:
        item.is_selected = item.id == message.id
    user_message = db.get(Message, message.reply_to_message_id)
    if user_message:
        memory_service.remember_turn(
            db,
            conversation.user_id,
            conversation.character_id,
            conversation.id,
            user_message.id,
            user_message.content,
            message.content,
        )
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)
    return message


@router.post(
    "/{conversation_id}/messages/{message_id}/regenerate",
    response_model=MessageRead,
)
def regenerate_message(
    conversation_id: str,
    message_id: str,
    payload: MessageRegenerate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = _owned_conversation(db, user, conversation_id)
    message = _assistant_message(db, conversation, message_id)
    if payload.stream:
        return StreamingResponse(
            _locked_regeneration_stream(db, conversation, message),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    try:
        with redis_gateway.conversation_lock(conversation.id):
            return roleplay_orchestrator.regenerate(db, conversation, message)
    except AlternativeLimitReached as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except LockBusy as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except (RuntimeError, httpx.HTTPError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI provider failed") from exc


@router.post(
    "/{conversation_id}/messages/{message_id}/continue",
    response_model=MessageRead,
)
def continue_message(
    conversation_id: str,
    message_id: str,
    payload: MessageRegenerate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = _owned_conversation(db, user, conversation_id)
    message = _assistant_message(db, conversation, message_id)
    if payload.stream:
        return StreamingResponse(
            _locked_continuation_stream(db, conversation, message),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    try:
        with redis_gateway.conversation_lock(conversation.id):
            return roleplay_orchestrator.continue_message(db, conversation, message)
    except LockBusy as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except (RuntimeError, httpx.HTTPError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI provider failed") from exc


@router.post(
    "/{conversation_id}/suggested-reply",
    response_model=SuggestedReplyRead,
)
def suggested_reply(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SuggestedReplyRead:
    conversation = _owned_conversation(db, user, conversation_id)
    try:
        with redis_gateway.conversation_lock(conversation.id):
            suggestion = roleplay_orchestrator.suggested_reply(db, conversation)
    except LockBusy as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except (RuntimeError, httpx.HTTPError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI provider failed") from exc
    return SuggestedReplyRead(suggestion=suggestion)


@router.delete(
    "/{conversation_id}/messages/{message_id}/rewind",
    response_model=RewindRead,
)
def rewind_to_message(
    conversation_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> RewindRead:
    conversation = _owned_conversation(db, user, conversation_id)
    try:
        with redis_gateway.conversation_lock(conversation.id):
            timeline = list(
                db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation.id)
                    .order_by(Message.created_at.asc(), Message.id.asc())
                )
            )
            target_index = next(
                (index for index, item in enumerate(timeline) if item.id == message_id),
                None,
            )
            if target_index is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
            deleted_ids = [item.id for item in timeline[target_index + 1 :]]
            if deleted_ids:
                db.execute(delete(Message).where(Message.id.in_(deleted_ids)))
            memory_service.clear_automatic_conversation_memories(
                db,
                user_id=user.id,
                conversation_id=conversation.id,
            )
            conversation.updated_at = timeline[target_index].created_at
            db.commit()
            return RewindRead(
                kept_message_id=message_id,
                deleted_count=len(deleted_ids),
            )
    except LockBusy as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def _locked_event_stream(
    db: Session, conversation: Conversation, content: str
) -> Generator[str, None, None]:
    try:
        with redis_gateway.conversation_lock(conversation.id):
            yield from roleplay_orchestrator.stream_message(db, conversation, content)
    except LockBusy as exc:
        yield roleplay_orchestrator.event(
            "error", {"code": "conversation_busy", "detail": str(exc)}
        )
    except (RuntimeError, httpx.HTTPError):
        db.rollback()
        yield roleplay_orchestrator.event("error", {"code": "provider_error"})


def _locked_regeneration_stream(
    db: Session, conversation: Conversation, message: Message
) -> Generator[str, None, None]:
    try:
        with redis_gateway.conversation_lock(conversation.id):
            yield from roleplay_orchestrator.stream_regeneration(db, conversation, message)
    except AlternativeLimitReached as exc:
        db.rollback()
        yield roleplay_orchestrator.event(
            "error", {"code": "alternative_limit", "detail": str(exc)}
        )
    except LockBusy as exc:
        yield roleplay_orchestrator.event(
            "error", {"code": "conversation_busy", "detail": str(exc)}
        )
    except (RuntimeError, httpx.HTTPError):
        db.rollback()
        yield roleplay_orchestrator.event("error", {"code": "provider_error"})


def _locked_continuation_stream(
    db: Session, conversation: Conversation, message: Message
) -> Generator[str, None, None]:
    try:
        with redis_gateway.conversation_lock(conversation.id):
            yield from roleplay_orchestrator.stream_continuation(
                db, conversation, message
            )
    except LockBusy as exc:
        yield roleplay_orchestrator.event(
            "error", {"code": "conversation_busy", "detail": str(exc)}
        )
    except (RuntimeError, httpx.HTTPError):
        db.rollback()
        yield roleplay_orchestrator.event("error", {"code": "provider_error"})
