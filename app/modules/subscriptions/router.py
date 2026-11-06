from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db.models import Subscription, User
from app.db.session import get_db
from app.modules.subscriptions.schemas import SubscriptionRead
from app.modules.subscriptions.service import subscription_service


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/current", response_model=SubscriptionRead)
def current_subscription(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> Subscription:
    return subscription_service.get_or_create(db, user.id)
