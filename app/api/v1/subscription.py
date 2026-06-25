import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.postgres import get_db
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.models.sql.subscription import Subscription, PlanType
from app.services.rate_limiter import get_query_count_today

router = APIRouter(prefix="/api/v1/subscription", tags=["subscription"])


class SubscriptionOut(BaseModel):
    workspace_id: str
    plan: str
    queries_per_day: int
    queries_used_today: int
    queries_remaining: int


class UpgradeRequest(BaseModel):
    plan: PlanType


@router.get("/{workspace_id}", response_model=SubscriptionOut)
async def get_subscription(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace)
        .where(
            Workspace.id == workspace_id,
            Workspace.owner_id == current_user.id,
        )
        .options(selectinload(Workspace.subscription))
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    sub = workspace.subscription
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    used_today = await get_query_count_today(str(workspace_id))
    remaining = max(0, sub.queries_per_day - used_today)

    return SubscriptionOut(
        workspace_id=str(workspace_id),
        plan=sub.plan,
        queries_per_day=sub.queries_per_day,
        queries_used_today=used_today,
        queries_remaining=remaining,
    )


@router.patch("/{workspace_id}", response_model=SubscriptionOut)
async def upgrade_subscription(
    workspace_id: uuid.UUID,
    payload: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace)
        .where(
            Workspace.id == workspace_id,
            Workspace.owner_id == current_user.id,
        )
        .options(selectinload(Workspace.subscription))
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    sub = workspace.subscription
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    sub.plan = payload.plan
    sub.queries_per_day = 10000 if payload.plan == PlanType.pro else 10
    await db.commit()
    await db.refresh(sub)

    used_today = await get_query_count_today(str(workspace_id))

    return SubscriptionOut(
        workspace_id=str(workspace_id),
        plan=sub.plan,
        queries_per_day=sub.queries_per_day,
        queries_used_today=used_today,
        queries_remaining=max(0, sub.queries_per_day - used_today),
    )