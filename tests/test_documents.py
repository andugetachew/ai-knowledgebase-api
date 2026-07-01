import io
import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

async def register_and_login(client, email: str) -> tuple[str, str]:
    """Returns (token, workspace_id)."""
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

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpassword123"},
    )
    token = login.json()["access_token"]

    # fetch workspace_id — add /api/v1/users/me or return from register
    # for now we grab it from the DB via a second call if you expose it,
    # or add workspace_id to UserOut (recommended — see note below)
    workspace_id = reg.json().get("workspace_id")
    return token, workspace_id


def pdf_file(name: str = "test.pdf") -> tuple:
    return (name, io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")


def txt_file(name: str = "test.txt") -> tuple:
    return (name, io.BytesIO(b"plain text content"), "text/plain")


def exe_file(name: str = "malware.exe") -> tuple:
    return (name, io.BytesIO(b"MZ fake exe"), "application/octet-stream")


# ── upload tests ──────────────────────────────────────────────────────────────

async def test_upload_pdf_success(client, workspace_id, auth_headers):
    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.pdf"
    assert data["file_type"] == "application/pdf"
    assert data["status"] in ("pending", "ready")
    assert data["workspace_id"] == workspace_id


async def test_upload_txt_success(client, workspace_id, auth_headers):
    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": txt_file()},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/plain"


async def test_upload_unsupported_file_type_fails(client, workspace_id, auth_headers):
    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": exe_file()},
        headers=auth_headers,
    )
    assert response.status_code == 400


async def test_upload_to_nonexistent_workspace_fails(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        f"/api/v1/documents/?workspace_id={fake_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_upload_without_token_fails(client, workspace_id):
    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
    )
    assert response.status_code == 401


async def test_upload_to_another_users_workspace_fails(client, workspace_id):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "intruder@test.com",
            "password": "testpassword123",
            "full_name": "Intruder",
            "workspace_name": "Intruder Workspace",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "intruder@test.com", "password": "testpassword123"},
    )
    intruder_token = login.json()["access_token"]
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=intruder_headers,
    )
    assert response.status_code == 403

async def test_list_documents_empty(client, workspace_id, auth_headers):
    response = await client.get(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["documents"] == []


async def test_list_documents_after_upload(client, workspace_id, auth_headers):
    await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )
    await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": txt_file()},
        headers=auth_headers,
    )
    response = await client.get(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_list_documents_without_token_fails(client, workspace_id):
    response = await client.get(
        f"/api/v1/documents/?workspace_id={workspace_id}",
    )
    assert response.status_code == 401


# ── delete tests ──────────────────────────────────────────────────────────────

async def test_delete_document_success(client, workspace_id, auth_headers):
    upload = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )
    document_id = upload.json()["id"]

    response = await client.delete(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    # confirm it's gone
    list_response = await client.get(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        headers=auth_headers,
    )
    assert list_response.json()["total"] == 0


async def test_delete_nonexistent_document_fails(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(
        f"/api/v1/documents/{fake_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_delete_without_token_fails(client, workspace_id):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.delete(f"/api/v1/documents/{fake_id}")
    assert response.status_code == 401

from kombu.exceptions import OperationalError
import app.api.v1.documents as documents_module


def huge_file(name: str = "huge.pdf") -> tuple:
    content = b"x" * (10 * 1024 * 1024 + 1)  # over MAX_FILE_SIZE
    return (name, io.BytesIO(content), "application/pdf")


async def test_upload_file_too_large(client, workspace_id, auth_headers):
    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": huge_file()},
        headers=auth_headers,
    )
    assert response.status_code == 400


async def test_upload_broker_unavailable(client, workspace_id, auth_headers, monkeypatch):
    def raise_broker_error(**kwargs):
        raise OperationalError("broker down")

    monkeypatch.setattr(documents_module.process_document, "delay", raise_broker_error)

    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )
    assert response.status_code == 503


async def test_reupload_creates_new_version(client, workspace_id, auth_headers):
    first = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )
    assert first.json()["version"] == 1

    second = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2
    assert second.json()["parent_document_id"] is not None


async def test_get_document_versions(client, workspace_id, auth_headers):
    first = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )
    document_id = first.json()["id"]

    await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": pdf_file()},
        headers=auth_headers,
    )

    response = await client.get(f"/api/v1/documents/{document_id}/versions", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_get_document_versions_not_found(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/v1/documents/{fake_id}/versions", headers=auth_headers)
    assert response.status_code == 404


async def test_ingest_url_success(client, workspace_id, auth_headers, monkeypatch):
    async def fake_extract(url):
        return "extracted content from url"

    monkeypatch.setattr(documents_module, "extract_text_from_url", fake_extract)

    response = await client.post(
        "/api/v1/documents/ingest-url",
        json={"url": "https://example.com/article", "workspace_id": workspace_id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "https://example.com/article"
    assert data["file_type"] == "text/html"


async def test_ingest_url_fetch_failure(client, workspace_id, auth_headers, monkeypatch):
    async def fake_extract(url):
        raise ValueError("connection refused")

    monkeypatch.setattr(documents_module, "extract_text_from_url", fake_extract)

    response = await client.post(
        "/api/v1/documents/ingest-url",
        json={"url": "https://bad-url.example", "workspace_id": workspace_id},
        headers=auth_headers,
    )
    assert response.status_code == 400


async def test_ingest_url_without_token_fails(client, workspace_id):
    response = await client.post(
        "/api/v1/documents/ingest-url",
        json={"url": "https://example.com", "workspace_id": workspace_id},
    )
    assert response.status_code == 401