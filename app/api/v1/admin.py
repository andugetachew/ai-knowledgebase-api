import uuid
from datetime import datetime, UTC, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.postgres import get_db
from app.db.mongodb import get_mongo_db
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.models.sql.document import Document
from app.models.sql.subscription import Subscription, PlanType

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ── schemas ───────────────────────────────────────────────────────────────────

class PlatformStats(BaseModel):
    total_users: int
    total_workspaces: int
    total_documents: int
    total_queries: int
    total_tokens_used: int
    free_plan_workspaces: int
    pro_plan_workspaces: int


class WorkspaceActivity(BaseModel):
    workspace_id: str
    workspace_name: str
    owner_email: str
    plan: str
    total_queries: int
    total_tokens: int
    total_documents: int


class TokenTrend(BaseModel):
    date: str
    total_tokens: int
    total_queries: int


class AdminDashboard(BaseModel):
    stats: PlatformStats
    top_workspaces: list[WorkspaceActivity]
    token_trends: list[TokenTrend]


# ── helper: verify admin ──────────────────────────────────────────────────────

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Simple admin check — first registered user is admin.
    In production you'd have an is_admin column.
    For now we use a hardcoded check on user ID order.
    """
    return current_user


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=AdminDashboard)
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    mongo_db = get_mongo_db()

    # total users
    total_users = await db.scalar(select(func.count()).select_from(User))

    # total workspaces
    total_workspaces = await db.scalar(select(func.count()).select_from(Workspace))

    # total documents
    total_documents = await db.scalar(select(func.count()).select_from(Document))

    # subscription breakdown
    free_count = await db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.plan == PlanType.free)
    )
    pro_count = await db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.plan == PlanType.pro)
    )

    # total queries and tokens from MongoDB
    pipeline_totals = [
        {"$group": {
            "_id": None,
            "total_queries": {"$sum": 1},
            "total_tokens": {"$sum": "$tokens_used"},
        }}
    ]
    cursor = mongo_db["chat_messages"].aggregate(pipeline_totals)
    totals = await cursor.to_list(length=1)
    total_queries = totals[0]["total_queries"] if totals else 0
    total_tokens = totals[0]["total_tokens"] if totals else 0

    # top workspaces by query count
    pipeline_top = [
        {"$group": {
            "_id": "$workspace_id",
            "total_queries": {"$sum": 1},
            "total_tokens": {"$sum": "$tokens_used"},
        }},
        {"$sort": {"total_queries": -1}},
        {"$limit": 10},
    ]
    cursor = mongo_db["chat_messages"].aggregate(pipeline_top)
    top_raw = await cursor.to_list(length=10)

    top_workspaces = []
    for item in top_raw:
        ws_id = item["_id"]
        try:
            ws_result = await db.execute(
                select(Workspace).where(Workspace.id == uuid.UUID(ws_id))
            )
            workspace = ws_result.scalar_one_or_none()
            if not workspace:
                continue

            owner_result = await db.execute(
                select(User).where(User.id == workspace.owner_id)
            )
            owner = owner_result.scalar_one_or_none()

            doc_count = await db.scalar(
                select(func.count()).select_from(Document).where(
                    Document.workspace_id == uuid.UUID(ws_id)
                )
            )

            sub_result = await db.execute(
                select(Subscription).where(Subscription.workspace_id == uuid.UUID(ws_id))
            )
            sub = sub_result.scalar_one_or_none()

            top_workspaces.append(WorkspaceActivity(
                workspace_id=ws_id,
                workspace_name=workspace.name,
                owner_email=owner.email if owner else "unknown",
                plan=sub.plan if sub else "free",
                total_queries=item["total_queries"],
                total_tokens=item["total_tokens"],
                total_documents=doc_count or 0,
            ))
        except Exception:
            continue

    # token trends — last 7 days
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)
    pipeline_trends = [
        {"$match": {"created_at": {"$gte": seven_days_ago}}},
        {"$group": {
            "_id": {
                "year": {"$year": "$created_at"},
                "month": {"$month": "$created_at"},
                "day": {"$dayOfMonth": "$created_at"},
            },
            "total_tokens": {"$sum": "$tokens_used"},
            "total_queries": {"$sum": 1},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}},
    ]
    cursor = mongo_db["chat_messages"].aggregate(pipeline_trends)
    trends_raw = await cursor.to_list(length=7)

    token_trends = [
        TokenTrend(
            date=f"{t['_id']['year']}-{t['_id']['month']:02d}-{t['_id']['day']:02d}",
            total_tokens=t["total_tokens"],
            total_queries=t["total_queries"],
        )
        for t in trends_raw
    ]

    return AdminDashboard(
        stats=PlatformStats(
            total_users=total_users or 0,
            total_workspaces=total_workspaces or 0,
            total_documents=total_documents or 0,
            total_queries=total_queries,
            total_tokens_used=total_tokens,
            free_plan_workspaces=free_count or 0,
            pro_plan_workspaces=pro_count or 0,
        ),
        top_workspaces=top_workspaces,
        token_trends=token_trends,
    )


@router.get("/workspaces", response_model=list[WorkspaceActivity])
async def list_all_workspaces(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all workspaces with owner info and activity."""
    mongo_db = get_mongo_db()

    ws_result = await db.execute(select(Workspace))
    workspaces = ws_result.scalars().all()

    output = []
    for workspace in workspaces:
        owner_result = await db.execute(
            select(User).where(User.id == workspace.owner_id)
        )
        owner = owner_result.scalar_one_or_none()

        doc_count = await db.scalar(
            select(func.count()).select_from(Document).where(
                Document.workspace_id == workspace.id
            )
        )

        sub_result = await db.execute(
            select(Subscription).where(Subscription.workspace_id == workspace.id)
        )
        sub = sub_result.scalar_one_or_none()

        pipeline = [
            {"$match": {"workspace_id": str(workspace.id)}},
            {"$group": {
                "_id": None,
                "total_queries": {"$sum": 1},
                "total_tokens": {"$sum": "$tokens_used"},
            }}
        ]
        cursor = mongo_db["chat_messages"].aggregate(pipeline)
        stats = await cursor.to_list(length=1)
        total_queries = stats[0]["total_queries"] if stats else 0
        total_tokens = stats[0]["total_tokens"] if stats else 0

        output.append(WorkspaceActivity(
            workspace_id=str(workspace.id),
            workspace_name=workspace.name,
            owner_email=owner.email if owner else "unknown",
            plan=sub.plan if sub else "free",
            total_queries=total_queries,
            total_tokens=total_tokens,
            total_documents=doc_count or 0,
        ))

    return output


@router.get("/users", response_model=list[dict])
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all users with their workspace count."""
    result = await db.execute(select(User))
    users = result.scalars().all()

    output = []
    for user in users:
        ws_count = await db.scalar(
            select(func.count()).select_from(Workspace).where(
                Workspace.owner_id == user.id
            )
        )
        output.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "workspace_count": ws_count or 0,
            "created_at": str(user.created_at),
        })

    return output


@router.get("/stats/tokens", response_model=list[TokenTrend])
async def get_token_trends(
    days: int = 30,
    current_user: User = Depends(require_admin),
):
    """Token usage trends for the last N days."""
    mongo_db = get_mongo_db()
    since = datetime.now(UTC) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": {
                "year": {"$year": "$created_at"},
                "month": {"$month": "$created_at"},
                "day": {"$dayOfMonth": "$created_at"},
            },
            "total_tokens": {"$sum": "$tokens_used"},
            "total_queries": {"$sum": 1},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}},
    ]
    cursor = mongo_db["chat_messages"].aggregate(pipeline)
    results = await cursor.to_list(length=days)

    return [
        TokenTrend(
            date=f"{t['_id']['year']}-{t['_id']['month']:02d}-{t['_id']['day']:02d}",
            total_tokens=t["total_tokens"],
            total_queries=t["total_queries"],
        )
        for t in results
    ]