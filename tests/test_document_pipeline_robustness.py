import io
import pytest
from unittest.mock import patch
from kombu.exceptions import OperationalError

from app.services.chunking_service import chunk_text


async def register_and_login(client, email: str) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "full_name": "Test User",
            "workspace_name": "Test Workspace",
        },
    )
    assert reg.status_code == 201
    workspace_id = reg.json()["workspace_id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    token = login.json()["access_token"]
    return token, workspace_id


# ── Bug 1: Celery broker unreachable at upload time ─────────────────────────

async def test_upload_returns_503_when_celery_broker_unreachable(client):
    token, workspace_id = await register_and_login(client, "pipeline1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.api.v1.documents.process_document.delay",
        side_effect=OperationalError("broker unreachable"),
    ):
        response = await client.post(
            f"/api/v1/documents/?workspace_id={workspace_id}",
            files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
            headers=headers,
        )

    assert response.status_code == 503


async def test_upload_marks_document_failed_when_broker_unreachable(client):
    token, workspace_id = await register_and_login(client, "pipeline2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.api.v1.documents.process_document.delay",
        side_effect=OperationalError("broker unreachable"),
    ):
        await client.post(
            f"/api/v1/documents/?workspace_id={workspace_id}",
            files={"file": ("test2.txt", io.BytesIO(b"hello world"), "text/plain")},
            headers=headers,
        )

    list_response = await client.get(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        headers=headers,
    )
    docs = list_response.json()["documents"]
    matching = [d for d in docs if d["filename"] == "test2.txt"]
    assert len(matching) == 1
    assert matching[0]["status"] == "failed"


# ── Bug 2: chunk_text pathological inputs ────────────────────────────────────

def test_chunk_text_raises_when_overlap_equals_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("a b c d e", chunk_size=50, overlap=50)


def test_chunk_text_raises_when_overlap_exceeds_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("a b c d e", chunk_size=10, overlap=20)


def test_chunk_text_raises_on_non_positive_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("a b c d e", chunk_size=0, overlap=0)


def test_chunk_text_terminates_with_valid_overlap():
    text = " ".join(["word"] * 1000)
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) > 0
    assert all(isinstance(c, str) for c in chunks)


def test_chunk_text_single_long_word_returns_one_chunk():
    text = "x" * 100_000  # no whitespace at all
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_input_returns_empty_list():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


# ── Bug 3: oversized extracted text gets truncated before chunking ──────────

async def test_upload_truncates_oversized_extracted_text(client):
    token, workspace_id = await register_and_login(client, "pipeline3@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 3,000,000 chars of plain text — exceeds MAX_EXTRACTED_TEXT_LENGTH (2,000,000)
    huge_text = ("word " * 600_000).encode()

    captured_content = {}

    def fake_delay(**kwargs):
        captured_content["content"] = kwargs["content"]

    with patch("app.api.v1.documents.process_document.delay", side_effect=fake_delay):
        response = await client.post(
            f"/api/v1/documents/?workspace_id={workspace_id}",
            files={"file": ("huge.txt", io.BytesIO(huge_text), "text/plain")},
            headers=headers,
        )

    assert response.status_code == 201
    assert len(captured_content["content"]) <= 2_000_000