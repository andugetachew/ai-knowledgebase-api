import uuid
from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.db.postgres import get_db
from app.db.mongodb import get_mongo_db
from app.db.redis import get_redis
from app.models.sql.user import User
from app.models.sql.workspace import Workspace

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


async def _verify_workspace(workspace_id: str, db: AsyncSession, current_user: User) -> Workspace:
    """Same ownership check pattern used in chat.py."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == uuid.UUID(workspace_id),
            Workspace.owner_id == current_user.id,
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


# ── 1. Time-series: queries over time ───────────────────────────────────────
@router.get("/{workspace_id}/queries-over-time")
async def queries_over_time(
    workspace_id: str,
    period: str = Query("7d", pattern="^[0-9]+[dh]$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace(workspace_id, db, current_user)
    mongo_db = get_mongo_db()

    amount = int(period[:-1])
    unit = period[-1]
    since = datetime.now(UTC) - (timedelta(hours=amount) if unit == "h" else timedelta(days=amount))

    # Group by hour if period is in hours or <= 2 days, otherwise by day
    group_by_hour = unit == "h" or amount <= 2
    date_format = "%Y-%m-%dT%H:00:00" if group_by_hour else "%Y-%m-%d"

    pipeline = [
        {"$match": {"workspace_id": workspace_id, "created_at": {"$gte": since}}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": date_format, "date": "$created_at"}},
                "query_count": {"$sum": 1},
                "total_tokens": {"$sum": "$tokens_used"},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    cursor = mongo_db["chat_messages"].aggregate(pipeline)
    buckets = [
        {"bucket": doc["_id"], "query_count": doc["query_count"], "total_tokens": doc["total_tokens"]}
        async for doc in cursor
    ]

    return {
        "workspace_id": workspace_id,
        "period": period,
        "granularity": "hour" if group_by_hour else "day",
        "buckets": buckets,
    }


# ── 2. Document analytics: most referenced documents ────────────────────────
@router.get("/{workspace_id}/top-documents")
async def top_documents(
    workspace_id: str,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace(workspace_id, db, current_user)
    mongo_db = get_mongo_db()

    # `sources` is a list[str] of document identifiers per chat_messages doc
    pipeline = [
        {"$match": {"workspace_id": workspace_id}},
        {"$unwind": "$sources"},
        {"$group": {"_id": "$sources", "reference_count": {"$sum": 1}}},
        {"$sort": {"reference_count": -1}},
        {"$limit": limit},
    ]

    cursor = mongo_db["chat_messages"].aggregate(pipeline)
    top_docs = [
        {"source": doc["_id"], "reference_count": doc["reference_count"]}
        async for doc in cursor
    ]

    return {"workspace_id": workspace_id, "top_documents": top_docs}


# ── 3. Real-time event streaming (SSE) ───────────────────────────────────────
@router.get("/{workspace_id}/stream")
async def analytics_stream(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events endpoint. Polls Redis live counters every 3s and
    pushes them to the client. Simpler than WebSocket for one-way dashboard data.
    """
    await _verify_workspace(workspace_id, db, current_user)
    redis = get_redis()

    async def event_generator():
        import asyncio
        import json

        while True:
            live_count = await redis.get(f"queries:live:{workspace_id}")
            payload = {
                "workspace_id": workspace_id,
                "active_queries_last_hour": int(live_count) if live_count else 0,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── 4. Performance metrics ───────────────────────────────────────────────────
@router.get("/{workspace_id}/performance")
async def performance_metrics(
    workspace_id: str,
    period: str = Query("7d", pattern="^[0-9]+[dh]$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace(workspace_id, db, current_user)
    mongo_db = get_mongo_db()

    amount = int(period[:-1])
    unit = period[-1]
    since = datetime.now(UTC) - (timedelta(hours=amount) if unit == "h" else timedelta(days=amount))

    pipeline = [
        {"$match": {"workspace_id": workspace_id, "created_at": {"$gte": since}}},
        {
            "$group": {
                "_id": None,
                "total_queries": {"$sum": 1},
                "avg_tokens_per_query": {"$avg": "$tokens_used"},
                "total_tokens": {"$sum": "$tokens_used"},
            }
        },
    ]

    cursor = mongo_db["chat_messages"].aggregate(pipeline)
    result = await cursor.to_list(length=1)

    if not result:
        return {
            "workspace_id": workspace_id,
            "period": period,
            "total_queries": 0,
            "avg_tokens_per_query": 0,
            "total_tokens": 0,
        }

    doc = result[0]
    return {
        "workspace_id": workspace_id,
        "period": period,
        "total_queries": doc["total_queries"],
        "avg_tokens_per_query": round(doc["avg_tokens_per_query"] or 0, 2),
        "total_tokens": doc["total_tokens"],
    }


# ── 5. Redis live counters ───────────────────────────────────────────────────
@router.get("/{workspace_id}/live")
async def live_activity(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_workspace(workspace_id, db, current_user)
    redis = get_redis()

    live_count = await redis.get(f"queries:live:{workspace_id}")

    return {
        "workspace_id": workspace_id,
        "active_queries_last_hour": int(live_count) if live_count else 0,
    }