from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None
    display_name: str | None = None


def _identity_from_bearer(authorization: str | None) -> Identity | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    if settings.allow_local_auth:
        try:
            claims = jwt.decode(
                token,
                settings.local_jwt_secret,
                algorithms=["HS256"],
                issuer="lumora-local",
            )
            return Identity(
                subject=claims["sub"],
                email=claims.get("email"),
                display_name=claims.get("name"),
            )
        except (jwt.PyJWTError, KeyError):
            pass
    if not settings.supabase_jwt_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token")

    try:
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token") from exc

    subject = claims.get("sub")
    if not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has no subject")
    metadata = claims.get("user_metadata") or {}
    return Identity(subject=subject, email=claims.get("email"), display_name=metadata.get("name"))


def current_user(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_name: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    identity = _identity_from_bearer(authorization)
    if identity is None:
        if not settings.allow_dev_auth:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
        identity = Identity(
            subject=x_user_id or "local-development-user",
            email=x_user_email or "local@lumora.test",
            display_name=x_user_name or "Local user",
        )

    user = db.scalar(
        select(User).where(
            or_(
                User.id == identity.subject,
                User.supabase_user_id == identity.subject,
                User.email == identity.email if identity.email else False,
            )
        )
    )
    if user:
        return user

    user = User(
        supabase_user_id=identity.subject,
        email=identity.email or f"{identity.subject}@auth.local",
        display_name=identity.display_name or (identity.email or "Lumora user").split("@")[0],
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        user = db.scalar(
            select(User).where(
                or_(
                    User.id == identity.subject,
                    User.supabase_user_id == identity.subject,
                    User.email == identity.email if identity.email else False,
                )
            )
        )
        if user:
            return user
        raise
    db.refresh(user)
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user
