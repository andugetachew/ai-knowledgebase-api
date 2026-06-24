from datetime import datetime, UTC
from pydantic import BaseModel, Field
from bson import ObjectId


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    conversation_id: str = Field(default_factory=lambda: str(ObjectId()))
    workspace_id: str
    user_id: str
    question: str
    answer: str
    sources: list[str] = []
    tokens_used: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))