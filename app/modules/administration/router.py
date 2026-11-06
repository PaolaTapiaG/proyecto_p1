from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.models import Character, Conversation, User
from app.db.session import get_db


router = APIRouter(prefix="/administration", tags=["Administration"])


@router.get("/summary")
def administration_summary(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> dict[str, int]:
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "characters": db.scalar(select(func.count()).select_from(Character)) or 0,
        "conversations": db.scalar(select(func.count()).select_from(Conversation)) or 0,
    }
