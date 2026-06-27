from datetime import datetime, UTC

from app.models.nosql.chunk import DocumentChunk
from app.models.nosql.usage_log import UsageLog


def test_document_chunk_creates_with_required_fields():
    chunk = DocumentChunk(
        document_id="doc-123",
        workspace_id="ws-456",
        content="some chunk text",
        chunk_index=0,
    )
    assert chunk.document_id == "doc-123"
    assert chunk.workspace_id == "ws-456"
    assert chunk.content == "some chunk text"
    assert chunk.chunk_index == 0
    assert chunk.embedding == []
    assert chunk.id is not None
    assert isinstance(chunk.created_at, datetime)


def test_document_chunk_accepts_embedding():
    chunk = DocumentChunk(
        document_id="doc-123", workspace_id="ws-456",
        content="text", chunk_index=1, embedding=[0.1, 0.2, 0.3],
    )
    assert chunk.embedding == [0.1, 0.2, 0.3]


def test_document_chunk_generates_unique_ids():
    chunk1 = DocumentChunk(document_id="d1", workspace_id="w1", content="a", chunk_index=0)
    chunk2 = DocumentChunk(document_id="d1", workspace_id="w1", content="b", chunk_index=1)
    assert chunk1.id != chunk2.id


def test_usage_log_creates_with_defaults():
    log = UsageLog(workspace_id="ws-1", user_id="user-1", action="query")
    assert log.workspace_id == "ws-1"
    assert log.user_id == "user-1"
    assert log.action == "query"
    assert log.tokens_used == 0
    assert log.id is not None
    assert isinstance(log.created_at, datetime)
    assert log.created_at.tzinfo == UTC


def test_usage_log_accepts_tokens_used():
    log = UsageLog(workspace_id="ws-1", user_id="user-1", action="upload", tokens_used=150)
    assert log.tokens_used == 150