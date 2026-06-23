import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_db
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.schemas.chat import ChunkResult, SearchRequest, SearchResponse
from app.services.embedding_service import generate_embedding
from app.services.retrieval_service import cosine_similarity

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def semantic_search(
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # verify workspace ownership
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == uuid.UUID(payload.workspace_id),
            Workspace.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    mongo_db = get_mongo_db()
    query_embedding = generate_embedding(payload.query)

    # fetch all chunks for this workspace
    cursor = mongo_db["chunks"].find({"workspace_id": payload.workspace_id})
    chunks = await cursor.to_list(length=500)

    if not chunks:
        return SearchResponse(query=payload.query, results=[], total=0)

    # score and rank
    scored = []
    for chunk in chunks:
        if not chunk.get("embedding"):
            continue
        score = cosine_similarity(query_embedding, chunk["embedding"])
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:payload.top_k]

    results = [
        ChunkResult(
            document_id=chunk.get("document_id", ""),
            content=chunk["content"],
            chunk_index=chunk.get("chunk_index", 0),
            score=round(score, 4),
        )
        for score, chunk in top
    ]

    return SearchResponse(query=payload.query, results=results, total=len(results))