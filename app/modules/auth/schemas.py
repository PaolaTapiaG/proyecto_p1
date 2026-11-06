from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthOptions(BaseModel):
    email_enabled: bool
    google_enabled: bool
    supabase_url: str | None
