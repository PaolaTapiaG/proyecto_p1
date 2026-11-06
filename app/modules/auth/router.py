from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from app.modules.auth.schemas import AuthOptions, AuthToken, LoginRequest, RegisterRequest
from app.modules.auth.security import hash_password, issue_token, verify_password


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/options", response_model=AuthOptions)
def auth_options() -> AuthOptions:
    return AuthOptions(
        email_enabled=settings.allow_local_auth or bool(settings.supabase_url),
        google_enabled=bool(settings.supabase_url and settings.supabase_anon_key),
        supabase_url=settings.supabase_url,
    )


@router.post("/register", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthToken:
    if not settings.allow_local_auth:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Local auth is disabled")
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    user = User(
        display_name=payload.display_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthToken(access_token=issue_token(user))


@router.post("/login", response_model=AuthToken)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthToken:
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User account is not active")
    return AuthToken(access_token=issue_token(user))
