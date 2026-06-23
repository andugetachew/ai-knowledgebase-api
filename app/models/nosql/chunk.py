
from datetime import datetime, UTC
from pydantic import BaseModel, Field
from bson import ObjectId


class DocumentChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    document_id: str
    workspace_id: str
    content: str
    chunk_index: int
    embedding: list[float] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"arbitrary_types_allowed": True}