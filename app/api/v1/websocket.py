import uuid
import json
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.postgres import get_db
from app.db.mongodb import get_mongo_db
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.models.nosql.chat_message import ChatMessage
from app.services.retrieval_service import retrieve_relevant_chunks

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])


async def get_user_from_token(token: str, db: AsyncSession) -> User | None:
    user_id = decode_access_token(token)
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one_or_none()


@router.websocket("/chat/{workspace_id}")
async def websocket_chat(
    websocket: WebSocket,
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
):
    await websocket.accept()

    try:
        # expect first message to be auth token
        auth_message = await websocket.receive_text()
        data = json.loads(auth_message)
        token = data.get("token")

        if not token:
            await websocket.send_json({"error": "Missing token"})
            await websocket.close(code=1008)
            return

        user = await get_user_from_token(token, db)
        if not user:
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close(code=1008)
            return

        # verify workspace ownership
        result = await db.execute(
            select(Workspace).where(
                Workspace.id == uuid.UUID(workspace_id),
                Workspace.owner_id == user.id,
            )
        )
        workspace = result.scalar_one_or_none()

        if not workspace:
            await websocket.send_json({"error": "Workspace not found"})
            await websocket.close(code=1008)
            return

        await websocket.send_json({"status": "connected", "workspace_id": workspace_id})

        # main message loop
        while True:
            message = await websocket.receive_text()
            payload = json.loads(message)
            question = payload.get("question", "").strip()

            if not question:
                await websocket.send_json({"error": "Empty question"})
                continue

            # retrieve relevant chunks
            mongo_db = get_mongo_db()
            chunks = await retrieve_relevant_chunks(
                query=question,
                workspace_id=workspace_id,
                db=mongo_db,
            )

            context = "\n\n".join([
                f"[Document: {chunk.get('document_id', 'unknown')}]\n{chunk['content']}"
                for chunk in chunks
            ]) if chunks else "No documents available."

            prompt = f"""You are a helpful assistant that answers questions based on the provided documents.

Context:
{context}

Question: {question}

Answer based only on the context above. If the answer is not in the context, say so clearly."""

            # stream response from Claude
            full_answer = ""
            tokens_used = 0

            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 1024,
                        "stream": True,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        if raw == "[DONE]":
                            break
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type")

                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                full_answer += text
                                await websocket.send_json({
                                    "type": "token",
                                    "content": text,
                                })

                        elif event_type == "message_delta":
                            usage = event.get("usage", {})
                            tokens_used = usage.get("output_tokens", 0)

                        elif event_type == "message_stop":
                            sources = list({c.get("document_id", "") for c in chunks})
                            await websocket.send_json({
                                "type": "done",
                                "sources": sources,
                                "tokens_used": tokens_used,
                            })

            # persist to MongoDB
            chat_msg = ChatMessage(
                workspace_id=workspace_id,
                user_id=str(user.id),
                question=question,
                answer=full_answer,
                sources=list({c.get("document_id", "") for c in chunks}),
                tokens_used=tokens_used,
            )
            await mongo_db["chat_messages"].insert_one(chat_msg.model_dump())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close(code=1011)
        except Exception:
            pass