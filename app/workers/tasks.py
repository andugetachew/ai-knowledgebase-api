import asyncio
from celery import Celery
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.services.chunking_service import chunk_text
from app.services.embedding_service import generate_embeddings_batch

celery_app = Celery(
    "tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


def run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_document(self, document_id: str, workspace_id: str, content: str):
    """
    Background task: chunk text, generate embeddings, store in MongoDB,
    update document status and chunk count in PostgreSQL.
    """
    try:
        run_async(_process_document_async(document_id, workspace_id, content))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _process_document_async(document_id: str, workspace_id: str, content: str):
    from app.models.sql.document import Document, DocumentStatus

    # setup DB connections
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    mongo_client = AsyncIOMotorClient(settings.mongo_url)
    mongo_db = mongo_client[settings.mongo_db_name]

    try:
        # chunk and embed
        chunks = chunk_text(content)
        if not chunks:
            status = DocumentStatus.failed
            chunk_count = 0
        else:
            embeddings = generate_embeddings_batch(chunks)
            chunk_docs = [
                {
                    "document_id": document_id,
                    "workspace_id": workspace_id,
                    "content": chunk,
                    "chunk_index": i,
                    "embedding": embeddings[i],
                }
                for i, chunk in enumerate(chunks)
            ]
            await mongo_db["chunks"].insert_many(chunk_docs)
            status = DocumentStatus.ready
            chunk_count = len(chunks)

        # update document in postgres
        async with SessionLocal() as db:
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            if document:
                document.status = status
                document.chunk_count = chunk_count
                await db.commit()

    finally:
        mongo_client.close()
        await engine.dispose()