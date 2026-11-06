from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db.models import User
from app.db.session import get_db
from app.modules.usage.service import usage_service


router = APIRouter(prefix="/usage", tags=["Usage"])


@router.get("/summary")
def get_usage_summary(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, int]:
    return usage_service.summary(db, user.id)
