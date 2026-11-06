from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    persona: str = Field(min_length=1, max_length=8000)
    details_json: dict = Field(
        default_factory=dict,
        validation_alias=AliasChoices("details_json", "metadata_json"),
    )
    scenario: str | None = Field(default=None, max_length=4000)
    greeting: str | None = Field(default=None, max_length=2000)
    visibility: Literal["private", "public"] = "private"
    avatar_path: str | None = Field(default=None, max_length=500)
    ai_model: str = Field(default="qwen3:8b", max_length=120)
    source_name: str | None = Field(default=None, max_length=180)
    source_type: Literal["original", "anime", "videogame", "film", "series", "book", "other"] = (
        "original"
    )
    research_enabled: bool = False


class CharacterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    name: str
    last_name: str | None
    description: str
    persona: str
    details_json: dict
    scenario: str | None
    greeting: str | None
    visibility: str
    avatar_path: str | None
    ai_model: str
    source_name: str | None
    source_type: str
    research_enabled: bool
    research_summary: str | None
    research_url: str | None
    research_updated_at: datetime | None
    total_chats: int
    total_likes: int
    created_at: datetime
    updated_at: datetime


class BotMemoryCreate(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=8000)
    importance: int = Field(default=1, ge=1, le=10)


class BotMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    bot_id: str
    key: str
    value: str
    importance: int
    created_at: datetime


class BotAssistRequest(BaseModel):
    field: Literal["greeting", "persona", "description", "scenario"]
    name: str = Field(min_length=1, max_length=120)
    notes: str = Field(min_length=3, max_length=4000)
    source_name: str | None = Field(default=None, max_length=180)


class BotAssistRead(BaseModel):
    field: str
    suggestion: str


BotCreate = CharacterCreate
BotRead = CharacterRead
