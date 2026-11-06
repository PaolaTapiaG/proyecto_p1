from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None
    display_name: str | None
    avatar_path: str | None
    status: str
    is_admin: bool
    adult_confirmed: bool
    created_at: datetime


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    avatar_path: str | None = Field(default=None, max_length=500)
    adult_confirmed: bool | None = None


class PublicUserRead(BaseModel):
    id: str
    display_name: str
    avatar_path: str | None
    created_at: datetime
    bots_created: int
    total_likes: int
    total_chats: int
    followers_count: int
    is_following: bool = False


class FeedbackCreate(BaseModel):
    kind: Literal["improvement", "bug"]
    message: str = Field(min_length=10, max_length=5000)
    contact_email: str | None = Field(default=None, max_length=255)


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    message: str
    status: str
    created_at: datetime


class SupportRead(BaseModel):
    discord_url: str | None
