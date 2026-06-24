import uuid
from bson import ObjectId
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

    # determine conversation_id
    conversation_id = payload.conversation_id or str(ObjectId())

    # fetch conversation history if continuing
    conversation_history = []
    if payload.conversation_id:
        cursor = mongo_db["chat_messages"].find(
            {
                "conversation_id": payload.conversation_id,
                "workspace_id": payload.workspace_id,
            },
            sort=[("created_at", 1)],
            limit=6,
        )
        conversation_history = await cursor.to_list(length=6)

    # retrieve relevant chunks
    chunks = await retrieve_relevant_chunks(
        query=payload.question,
        workspace_id=payload.workspace_id,
        db=mongo_db,
    )

    # generate answer with history
    result_data = await generate_answer(
        question=payload.question,
        context_chunks=chunks,
        conversation_history=conversation_history,
    )

    # save message
    message = ChatMessage(
        conversation_id=conversation_id,
        workspace_id=payload.workspace_id,
        user_id=str(current_user.id),
        question=payload.question,
        answer=result_data["answer"],
        sources=result_data["sources"],
        tokens_used=result_data["tokens_used"],
    )
    await mongo_db["chat_messages"].insert_one(message.model_dump())

    return ChatResponse(
        answer=result_data["answer"],
        sources=result_data["sources"],
        tokens_used=result_data["tokens_used"],
        conversation_id=conversation_id,
    )


@router.get("/conversations/{workspace_id}", response_model=list[dict])
async def list_conversations(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == uuid.UUID(workspace_id),
            Workspace.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    mongo_db = get_mongo_db()

    pipeline = [
        {"$match": {"workspace_id": workspace_id}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$conversation_id",
            "last_question": {"$first": "$question"},
            "last_message_at": {"$first": "$created_at"},
            "message_count": {"$sum": 1},
        }},
        {"$sort": {"last_message_at": -1}},
        {"$limit": 20},
    ]

    cursor = mongo_db["chat_messages"].aggregate(pipeline)
    conversations = await cursor.to_list(length=20)

    return [
        {
            "conversation_id": c["_id"],
            "last_question": c["last_question"],
            "last_message_at": str(c["last_message_at"]),
            "message_count": c["message_count"],
        }
        for c in conversations
    ]


@router.get("/conversations/{workspace_id}/{conversation_id}", response_model=list[dict])
async def get_conversation(
    workspace_id: str,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
        {"conversation_id": conversation_id, "workspace_id": workspace_id},
        sort=[("created_at", 1)],
    )
    messages = await cursor.to_list(length=100)

    return [
        {
            "question": m["question"],
            "answer": m["answer"],
            "sources": m.get("sources", []),
            "tokens_used": m.get("tokens_used", 0),
            "created_at": str(m.get("created_at", "")),
        }
        for m in messages
    ]