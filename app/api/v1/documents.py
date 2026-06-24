import uuid
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.postgres import get_db
from app.models.sql.document import Document, DocumentStatus
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.schemas.document import DocumentOut, DocumentList
from app.services.document_processor import extract_text, extract_text_from_url
from app.workers.tasks import process_document

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

ALLOWED_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class URLIngestRequest(BaseModel):
    url: str
    workspace_id: uuid.UUID


@router.post("/", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_id == current_user.id,
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")

    try:
        text = extract_text(contents, file.content_type)
    except Exception:
        text = contents.decode("utf-8", errors="ignore")

    document = Document(
        workspace_id=workspace_id,
        filename=file.filename,
        file_type=file.content_type,
        file_size=len(contents),
        status=DocumentStatus.pending,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    process_document.delay(
        document_id=str(document.id),
        workspace_id=str(workspace_id),
        content=text,
    )

    return document


@router.post("/ingest-url", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def ingest_url(
    payload: URLIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == payload.workspace_id,
            Workspace.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    try:
        text = await extract_text_from_url(payload.url)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to fetch URL: {str(e)}")

    document = Document(
        workspace_id=payload.workspace_id,
        filename=payload.url,
        file_type="text/html",
        file_size=len(text.encode()),
        status=DocumentStatus.pending,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    process_document.delay(
        document_id=str(document.id),
        workspace_id=str(payload.workspace_id),
        content=text,
    )

    return document


@router.get("/", response_model=DocumentList)
async def list_documents(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    docs = await db.execute(
        select(Document).where(Document.workspace_id == workspace_id)
    )
    documents = docs.scalars().all()
    return DocumentList(total=len(documents), documents=documents)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    ws_result = await db.execute(
        select(Workspace).where(
            Workspace.id == document.workspace_id,
            Workspace.owner_id == current_user.id,
        )
    )
    if not ws_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await db.delete(document)
    await db.commit()