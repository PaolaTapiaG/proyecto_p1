from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserPersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    gender_expression: str | None = Field(default=None, max_length=80)
    personality: str = Field(min_length=1, max_length=6000)
    description: str | None = Field(default=None, max_length=3000)
    avatar_path: str | None = Field(default=None, max_length=500)


class UserPersonaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    gender_expression: str | None
    personality: str
    description: str | None
    avatar_path: str | None
    status: str
    created_at: datetime
    updated_at: datetime
