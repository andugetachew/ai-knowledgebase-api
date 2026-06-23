import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.sql.document import DocumentStatus


class DocumentOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    chunk_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentList(BaseModel):
    total: int
    documents: list[DocumentOut]