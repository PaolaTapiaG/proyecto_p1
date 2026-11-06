from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth import current_user
from app.db.models import Character, Conversation, User, UserFeedback, UserFollow
from app.db.session import get_db
from app.modules.users.schemas import (
    FeedbackCreate,
    FeedbackRead,
    PublicUserRead,
    SupportRead,
    UserRead,
    UserUpdate,
)
from app.modules.characters.schemas import CharacterRead


router = APIRouter(prefix="/users", tags=["Users"])


def _public_author(db: Session, author: User, viewer: User) -> PublicUserRead:
    counts = db.execute(
        select(
            func.count(Character.id),
            func.coalesce(func.sum(Character.total_likes), 0),
            func.coalesce(func.sum(Character.total_chats), 0),
        ).where(Character.owner_id == author.id, Character.visibility == "public")
    ).one()
    followers_count = db.scalar(
        select(func.count(UserFollow.follower_id)).where(UserFollow.author_id == author.id)
    ) or 0
    is_following = bool(db.get(UserFollow, (viewer.id, author.id)))
    return PublicUserRead(
        id=author.id,
        display_name=author.display_name,
        avatar_path=author.avatar_path,
        created_at=author.created_at,
        bots_created=int(counts[0]),
        total_likes=int(counts[1]),
        total_chats=int(counts[2]),
        followers_count=int(followers_count),
        is_following=is_following,
    )


@router.get("/me", response_model=UserRead)
def get_profile(user: User = Depends(current_user)) -> User:
    return user


@router.patch("/me", response_model=UserRead)
def update_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> User:
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(user, field, value)
    if changes.get("adult_confirmed") is False:
        db.execute(
            update(Conversation)
            .where(Conversation.user_id == user.id)
            .values(mature_content_enabled=False)
        )
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/feedback", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED
)
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> UserFeedback:
    feedback = UserFeedback(user_id=user.id, **payload.model_dump())
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/support", response_model=SupportRead)
def support_options() -> SupportRead:
    return SupportRead(discord_url=settings.discord_support_url)


@router.get("/search", response_model=list[PublicUserRead])
def search_authors(
    q: str,
    limit: int = 12,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[PublicUserRead]:
    query = q.strip()
    if len(query) < 2:
        return []
    safe_limit = min(max(limit, 1), 30)
    authors = db.scalars(
        select(User)
        .join(Character, Character.owner_id == User.id)
        .where(
            User.status == "active",
            Character.visibility == "public",
            User.display_name.ilike(f"%{query}%"),
        )
        .group_by(User.id)
        .order_by(func.count(Character.id).desc(), User.display_name.asc())
        .limit(safe_limit)
    ).all()
    return [_public_author(db, author, user) for author in authors]


@router.post("/{user_id}/follow", response_model=PublicUserRead)
def follow_author(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> PublicUserRead:
    if user_id == user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot follow yourself")
    author = db.get(User, user_id)
    if not author or author.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Author not found")
    if not db.get(UserFollow, (user.id, author.id)):
        db.add(UserFollow(follower_id=user.id, author_id=author.id))
        db.commit()
    return _public_author(db, author, user)


@router.delete("/{user_id}/follow", response_model=PublicUserRead)
def unfollow_author(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> PublicUserRead:
    author = db.get(User, user_id)
    if not author or author.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Author not found")
    follow = db.get(UserFollow, (user.id, author.id))
    if follow:
        db.delete(follow)
        db.commit()
    return _public_author(db, author, user)


@router.get("/{user_id}/bots", response_model=list[CharacterRead])
def public_author_bots(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> list[Character]:
    author = db.get(User, user_id)
    if not author or author.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Author not found")
    return list(
        db.scalars(
            select(Character)
            .where(Character.owner_id == author.id, Character.visibility == "public")
            .order_by(Character.total_likes.desc(), Character.created_at.desc())
        )
    )


@router.get("/{user_id}/public", response_model=PublicUserRead)
def public_profile(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
) -> PublicUserRead:
    author = db.get(User, user_id)
    if not author or author.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Author not found")
    return _public_author(db, author, _)
