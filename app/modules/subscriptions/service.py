from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Subscription


class SubscriptionService:
    def get_or_create(self, db: Session, user_id: str) -> Subscription:
        subscription = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
        if subscription:
            return subscription
        subscription = Subscription(user_id=user_id, plan="local", status="active")
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        return subscription


subscription_service = SubscriptionService()
