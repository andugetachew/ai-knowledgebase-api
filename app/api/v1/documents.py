import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.postgres import get_db
from app.models.sql.document import Document, DocumentStatus
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.schemas.document import DocumentOut, DocumentList
from app.services.chunking_service import chunk_text
from app.services.embedding_service import generate_embeddings_batch
from app.db.mongodb import get_mongo_db


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

ALLOWED_TYPES = {"application/pdf", "text/plain", "text/markdown"}
MAX_FILE_SIZE = 10 * 1024 * 1024


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

    content_text = contents.decode("utf-8", errors="ignore")
    chunks = chunk_text(content_text)

    if chunks:
        embeddings = generate_embeddings_batch(chunks)
        mongo_db = get_mongo_db()

        chunk_docs = [
            {
                "document_id": str(document.id),
                "workspace_id": str(workspace_id),
                "content": chunk,
                "chunk_index": i,
                "embedding": embeddings[i],
            }
            for i, chunk in enumerate(chunks)
        ]
        await mongo_db["chunks"].insert_many(chunk_docs)

        document.chunk_count = len(chunks)
        document.status = DocumentStatus.ready
        await db.commit()
        content_text = contents.decode("utf-8", errors="ignore")

        from app.workers.tasks import process_document
        process_document.delay(
            document_id=str(document.id),
            workspace_id=str(workspace_id),
            content=content_text,
        )
        await db.refresh(document)

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