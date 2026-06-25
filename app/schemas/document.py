import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    status: str
    version: int = 1
    parent_document_id: uuid.UUID | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentList(BaseModel):
    total: int
    documents: list[DocumentOut]