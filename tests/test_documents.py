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