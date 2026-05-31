"""Per-project usage accounting (tokens, images, estimated cost) and budgets."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import UsageRecord

# Rough USD estimates so the UI can show a cost. Adjust to your real pricing.
TOKEN_COST_PER_1K = 0.005
IMAGE_COST_EACH = 0.04


def _today() -> str:
    return date.today().isoformat()


def _get_or_create(db: Session, project_id: str, day: str | None = None) -> UsageRecord:
    day = day or _today()
    record = db.scalar(
        select(UsageRecord).where(
            UsageRecord.project_id == project_id, UsageRecord.day == day
        )
    )
    if not record:
        record = UsageRecord(project_id=project_id, day=day)
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def record_usage(
    db: Session, project_id: str, *, tokens: int = 0, images: int = 0
) -> UsageRecord:
    record = _get_or_create(db, project_id)
    record.tokens += int(tokens)
    record.images += int(images)
    record.cost_usd = round(
        (record.tokens / 1000.0) * TOKEN_COST_PER_1K + record.images * IMAGE_COST_EACH,
        4,
    )
    db.commit()
    db.refresh(record)
    return record


def usage_summary(db: Session, project_id: str) -> dict:
    record = _get_or_create(db, project_id)
    token_budget = settings.daily_token_budget
    gen_budget = settings.daily_generation_budget
    return {
        "day": record.day,
        "tokens": record.tokens,
        "images": record.images,
        "cost_usd": record.cost_usd,
        "token_budget": token_budget,
        "generation_budget": gen_budget,
        "tokens_remaining": max(token_budget - record.tokens, 0) if token_budget else None,
        "generations_remaining": max(gen_budget - record.images, 0) if gen_budget else None,
    }


def budget_exceeded(db: Session, project_id: str) -> bool:
    record = _get_or_create(db, project_id)
    if settings.daily_token_budget and record.tokens >= settings.daily_token_budget:
        return True
    if settings.daily_generation_budget and record.images >= settings.daily_generation_budget:
        return True
    return False
