from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversationCreate(BaseModel):
    character_id: str
    user_persona_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=180)
    creative_mode: bool = True
    auto_roleplay_user: bool = False
    story_preferences: str | None = Field(default=None, max_length=4000)
    minimum_paragraphs: int = Field(default=8, ge=8, le=12)
    mature_content_enabled: bool = False


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    character_id: str
    user_persona_id: str | None
    title: str
    creative_mode: bool
    auto_roleplay_user: bool
    story_preferences: str | None
    minimum_paragraphs: int
    mature_content_enabled: bool
    status: str
    created_at: datetime
    updated_at: datetime


class MessageSend(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    stream: bool = False


class MessageRegenerate(BaseModel):
    stream: bool = False


class SuggestedReplyRead(BaseModel):
    suggestion: str


class RewindRead(BaseModel):
    kept_message_id: str
    deleted_count: int


class ConversationSettingsUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    creative_mode: bool | None = None
    auto_roleplay_user: bool | None = None
    story_preferences: str | None = Field(default=None, max_length=4000)
    minimum_paragraphs: int | None = Field(default=None, ge=8, le=12)
    mature_content_enabled: bool | None = None
    status: Literal["active", "archived"] | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender: str
    content: str
    reply_to_message_id: str | None
    alternative_index: int
    is_selected: bool
    token_count: int
    moderation_status: str
    metadata_json: dict
    created_at: datetime


class ConversationMemoryCreate(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=3, max_length=8000)
    category: Literal["fact", "relationship", "timeline", "summary"] = "fact"
    importance: int = Field(default=10, ge=5, le=10)


class ConversationMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bot_id: str
    conversation_id: str | None
    key: str
    value: str
    importance: int
    created_at: datetime
    category: str = "fact"

    @model_validator(mode="after")
    def infer_category(self) -> "ConversationMemoryRead":
        if self.key.startswith("memory:"):
            self.category = self.key.split(":", 2)[1]
        elif self.key.startswith("timeline:") or self.key.startswith("turn:"):
            self.category = "timeline"
        elif self.key == "auto:summary":
            self.category = "summary"
        return self
