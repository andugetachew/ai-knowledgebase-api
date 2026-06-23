import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.postgres import get_db
from app.db.mongodb import get_mongo_db
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.models.nosql.chat_message import ChatMessage
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.retrieval_service import retrieve_relevant_chunks
from app.services.llm_service import generate_answer

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
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
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    mongo_db = get_mongo_db()

    # retrieve relevant chunks
    chunks = await retrieve_relevant_chunks(
        query=payload.question,
        workspace_id=payload.workspace_id,
        db=mongo_db,
    )

    # generate answer
    result = await generate_answer(
        question=payload.question,
        context_chunks=chunks,
    )

    # save chat message to MongoDB
    message = ChatMessage(
        workspace_id=payload.workspace_id,
        user_id=str(current_user.id),
        question=payload.question,
        answer=result["answer"],
        sources=result["sources"],
        tokens_used=result["tokens_used"],
    )
    await mongo_db["chat_messages"].insert_one(message.model_dump())
    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        tokens_used=result["tokens_used"],
    )