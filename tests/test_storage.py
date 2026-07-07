import io
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from botocore.exceptions import ClientError

from app.services.storage_service import upload_file, download_file, delete_file, get_presigned_url


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


# ── Storage service unit tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_file_returns_storage_key():
    mock_client = MagicMock()
    mock_client.put_object = MagicMock()

    with patch("app.services.storage_service.get_s3_client", return_value=mock_client):
        key = await upload_file(
            file_bytes=b"hello world",
            filename="test.txt",
            content_type="text/plain",
            workspace_id="ws-123",
        )

    assert key.startswith("documents/ws-123/")
    assert key.endswith(".txt")
    mock_client.put_object.assert_called_once()


@pytest.mark.asyncio
async def test_download_file_returns_bytes():
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"file content"
    mock_client.get_object.return_value = {"Body": mock_body}

    with patch("app.services.storage_service.get_s3_client", return_value=mock_client):
        content = await download_file("documents/ws-123/test.txt")

    assert content == b"file content"


@pytest.mark.asyncio
async def test_download_file_raises_on_missing_key():
    mock_client = MagicMock()
    mock_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
        "GetObject"
    )

    with patch("app.services.storage_service.get_s3_client", return_value=mock_client):
        with pytest.raises(FileNotFoundError):
            await download_file("documents/ws-123/missing.txt")


@pytest.mark.asyncio
async def test_delete_file_calls_s3():
    mock_client = MagicMock()

    with patch("app.services.storage_service.get_s3_client", return_value=mock_client):
        await delete_file("documents/ws-123/test.txt")

    mock_client.delete_object.assert_called_once()


def test_get_presigned_url_returns_url():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://storage.example.com/signed-url"

    with patch("app.services.storage_service.get_s3_client", return_value=mock_client):
        url = get_presigned_url("documents/ws-123/test.txt")

    assert url == "https://storage.example.com/signed-url"


# ── API integration tests ─────────────────────────────────────────────────────

async def test_upload_saves_storage_key(client):
    token, workspace_id = await register_and_login(client, "storage1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.documents.upload_file", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "documents/ws-123/abc.txt"

        response = await client.post(
            f"/api/v1/documents/?workspace_id={workspace_id}",
            files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
            headers=headers,
        )

    assert response.status_code == 201
    mock_upload.assert_called_once()


async def test_upload_succeeds_even_if_storage_fails(client):
    """Storage failure should not prevent document creation."""
    token, workspace_id = await register_and_login(client, "storage2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.api.v1.documents.upload_file",
        new_callable=AsyncMock,
        side_effect=Exception("S3 connection refused"),
    ):
        response = await client.post(
            f"/api/v1/documents/?workspace_id={workspace_id}",
            files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
            headers=headers,
        )

    assert response.status_code == 201


async def test_download_url_no_storage_key_returns_404(client):
    token, workspace_id = await register_and_login(client, "storage3@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.documents.upload_file", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = None

        upload = await client.post(
            f"/api/v1/documents/?workspace_id={workspace_id}",
            files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
            headers=headers,
        )

    document_id = upload.json()["id"]
    response = await client.get(
        f"/api/v1/documents/{document_id}/download-url",
        headers=headers,
    )
    assert response.status_code == 404


async def test_delete_document_cleans_up_storage(client):
    token, workspace_id = await register_and_login(client, "storage4@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.documents.upload_file", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "documents/ws-123/abc.txt"

        upload = await client.post(
            f"/api/v1/documents/?workspace_id={workspace_id}",
            files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
            headers=headers,
        )

    document_id = upload.json()["id"]

    with patch("app.api.v1.documents.delete_file", new_callable=AsyncMock) as mock_delete:
        response = await client.delete(
            f"/api/v1/documents/{document_id}",
            headers=headers,
        )

    assert response.status_code == 204
    mock_delete.assert_called_once_with("documents/ws-123/abc.txt")