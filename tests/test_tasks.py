import pytest
from celery.exceptions import Retry

from app.workers import tasks as tasks_module


class FakeDocument:
    def __init__(self):
        self.status = None


class FakeResult:
    def __init__(self, document):
        self._document = document

    def scalar_one_or_none(self):
        return self._document


class FakeDBSession:
    def __init__(self, document):
        self._document = document

    async def execute(self, stmt):
        return FakeResult(self._document)

    async def commit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSessionLocal:
    def __init__(self, document):
        self._document = document

    def __call__(self):
        return FakeDBSession(self._document)


class FakeEngine:
    async def dispose(self):
        pass


class FakeCollection:
    def __init__(self):
        self.inserted = []

    async def insert_many(self, docs):
        self.inserted.extend(docs)


class FakeMongoDB:
    def __init__(self):
        self.chunks = FakeCollection()

    def __getitem__(self, name):
        return self.chunks


class FakeMongoClient:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return self._db

    def close(self):
        pass


def test_run_async_executes_coroutine():
    async def sample():
        return 42

    assert tasks_module.run_async(sample()) == 42


async def test_process_document_async_success(monkeypatch):
    from app.models.sql.document import DocumentStatus

    document = FakeDocument()
    fake_mongo_db = FakeMongoDB()

    monkeypatch.setattr(tasks_module, "create_async_engine", lambda url: FakeEngine())
    monkeypatch.setattr(tasks_module, "async_sessionmaker", lambda **kwargs: FakeSessionLocal(document))
    monkeypatch.setattr(tasks_module, "AsyncIOMotorClient", lambda url: FakeMongoClient(fake_mongo_db))
    monkeypatch.setattr(tasks_module, "chunk_text", lambda content: ["chunk one", "chunk two"])
    monkeypatch.setattr(tasks_module, "generate_embeddings_batch", lambda chunks: [[0.1], [0.2]])

    await tasks_module._process_document_async(
        document_id="doc-123", workspace_id="ws-123", content="some content", version=1,
    )

    assert document.status == DocumentStatus.completed
    assert len(fake_mongo_db.chunks.inserted) == 2


async def test_process_document_async_empty_chunks(monkeypatch):
    from app.models.sql.document import DocumentStatus

    document = FakeDocument()
    fake_mongo_db = FakeMongoDB()

    monkeypatch.setattr(tasks_module, "create_async_engine", lambda url: FakeEngine())
    monkeypatch.setattr(tasks_module, "async_sessionmaker", lambda **kwargs: FakeSessionLocal(document))
    monkeypatch.setattr(tasks_module, "AsyncIOMotorClient", lambda url: FakeMongoClient(fake_mongo_db))
    monkeypatch.setattr(tasks_module, "chunk_text", lambda content: [])

    await tasks_module._process_document_async(
        document_id="doc-456", workspace_id="ws-456", content="", version=1,
    )

    assert document.status == DocumentStatus.failed
    assert len(fake_mongo_db.chunks.inserted) == 0


async def test_process_document_async_document_not_found(monkeypatch):
    fake_mongo_db = FakeMongoDB()

    monkeypatch.setattr(tasks_module, "create_async_engine", lambda url: FakeEngine())
    monkeypatch.setattr(tasks_module, "async_sessionmaker", lambda **kwargs: FakeSessionLocal(None))
    monkeypatch.setattr(tasks_module, "AsyncIOMotorClient", lambda url: FakeMongoClient(fake_mongo_db))
    monkeypatch.setattr(tasks_module, "chunk_text", lambda content: ["chunk"])
    monkeypatch.setattr(tasks_module, "generate_embeddings_batch", lambda chunks: [[0.1]])

    # document lookup returns None -> should not raise
    await tasks_module._process_document_async(
        document_id="doc-789", workspace_id="ws-789", content="content", version=1,
    )

from celery.exceptions import Retry as CeleryRetry

def test_process_document_retries_on_failure(monkeypatch):
    def fake_run_async_raises(coro):
        coro.close()
        raise RuntimeError("db connection failed")

    def fake_retry(exc=None, **kwargs):
        raise CeleryRetry("Task can be retried", exc)

    monkeypatch.setattr(tasks_module, "run_async", fake_run_async_raises)
    monkeypatch.setattr(tasks_module.process_document, "retry", fake_retry)

    with pytest.raises(CeleryRetry):
        tasks_module.process_document(
            document_id="doc-1", workspace_id="ws-1", content="text", version=1
        )