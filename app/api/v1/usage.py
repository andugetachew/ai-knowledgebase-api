import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models.sql.document import Document
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.schemas.chat import QueryLog, WorkspaceStats

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


@router.get("/{workspace_id}/stats", response_model=WorkspaceStats)
async def get_workspace_stats(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # verify ownership
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == uuid.UUID(workspace_id),
            Workspace.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    # check cache first
    redis = get_redis()
    cache_key = f"stats:{workspace_id}"
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return WorkspaceStats(**json.loads(cached))

    # total documents from postgres
    doc_result = await db.execute(
        select(func.count()).where(Document.workspace_id == uuid.UUID(workspace_id))
    )
    total_documents = doc_result.scalar() or 0

    # total chunks and queries from mongodb
    mongo_db = get_mongo_db()
    total_chunks = await mongo_db["chunks"].count_documents({"workspace_id": workspace_id})
    total_queries = await mongo_db["chat_messages"].count_documents({"workspace_id": workspace_id})

    # total tokens used
    pipeline = [
        {"$match": {"workspace_id": workspace_id}},
        {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}},
    ]
    token_result = await mongo_db["chat_messages"].aggregate(pipeline).to_list(1)
    total_tokens = token_result[0]["total"] if token_result else 0

    stats = WorkspaceStats(
        workspace_id=workspace_id,
        total_documents=total_documents,
        total_chunks=total_chunks,
        total_queries=total_queries,
        total_tokens_used=total_tokens,
    )

    # store in cache
    if redis:
        await redis.setex(cache_key, 60 * 5, stats.model_dump_json())

    return stats


@router.get("/{workspace_id}/history", response_model=list[QueryLog])
async def get_query_history(
    workspace_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # verify ownership
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == uuid.UUID(workspace_id),
            Workspace.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    mongo_db = get_mongo_db()
    cursor = mongo_db["chat_messages"].find(
        {"workspace_id": workspace_id},
        sort=[("created_at", -1)],
        limit=limit,
    )
    messages = await cursor.to_list(length=limit)

    return [
        QueryLog(
            question=m["question"],
            answer=m["answer"],
            sources=m.get("sources", []),
            tokens_used=m.get("tokens_used", 0),
            created_at=str(m.get("created_at", "")),
        )
        for m in messages
    ]