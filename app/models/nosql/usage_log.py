from datetime import datetime, UTC
from pydantic import BaseModel, Field
from bson import ObjectId


class UsageLog(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    workspace_id: str
    user_id: str
    action: str        # "upload", "query", "delete"
    tokens_used: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))