from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import UsageRecord


class UsageService:
    def record(
        self,
        db: Session,
        *,
        user_id: str,
        conversation_id: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> UsageRecord:
        record = UsageRecord(
            user_id=user_id,
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        db.add(record)
        return record

    def summary(self, db: Session, user_id: str) -> dict[str, int]:
        row = db.execute(
            select(
                func.coalesce(func.sum(UsageRecord.prompt_tokens), 0),
                func.coalesce(func.sum(UsageRecord.completion_tokens), 0),
                func.coalesce(func.sum(UsageRecord.cost_micros), 0),
            ).where(UsageRecord.user_id == user_id)
        ).one()
        return {
            "prompt_tokens": row[0],
            "completion_tokens": row[1],
            "cost_micros": row[2],
        }


usage_service = UsageService()
