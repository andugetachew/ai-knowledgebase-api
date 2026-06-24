import io
from unittest.mock import AsyncMock, patch


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


async def test_upload_csv_success(client):
    token, workspace_id = await register_and_login(client, "proc1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = b"name,age,city\nAlice,30,NYC\nBob,25,LA"
    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": ("data.csv", io.BytesIO(csv_content), "text/csv")},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/csv"
    assert response.json()["status"] == "pending"


async def test_upload_docx_success(client):
    token, workspace_id = await register_and_login(client, "proc2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    from docx import Document
    doc = Document()
    doc.add_paragraph("This is a test document.")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": (
            "test.docx",
            buf,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


async def test_upload_unsupported_type_still_fails(client):
    token, workspace_id = await register_and_login(client, "proc3@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": ("file.exe", io.BytesIO(b"binary"), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 400


async def test_ingest_url_success(client):
    token, workspace_id = await register_and_login(client, "proc4@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.api.v1.documents.extract_text_from_url",
        new_callable=AsyncMock,
        return_value="This is the extracted web page content.",
    ):
        response = await client.post(
            "/api/v1/documents/ingest-url",
            json={"url": "https://example.com", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "https://example.com"
    assert data["file_type"] == "text/html"
    assert data["status"] == "pending"


async def test_ingest_url_invalid_url_fails(client):
    token, workspace_id = await register_and_login(client, "proc5@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.api.v1.documents.extract_text_from_url",
        new_callable=AsyncMock,
        side_effect=Exception("Connection failed"),
    ):
        response = await client.post(
            "/api/v1/documents/ingest-url",
            json={"url": "https://this-does-not-exist-xyz.com", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 400


async def test_ingest_url_wrong_workspace_fails(client):
    token, _ = await register_and_login(client, "proc6@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    with patch(
        "app.api.v1.documents.extract_text_from_url",
        new_callable=AsyncMock,
        return_value="content",
    ):
        response = await client.post(
            "/api/v1/documents/ingest-url",
            json={"url": "https://example.com", "workspace_id": fake_id},
            headers=headers,
        )

    assert response.status_code == 404


async def test_ingest_url_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "proc7@test.com")

    response = await client.post(
        "/api/v1/documents/ingest-url",
        json={"url": "https://example.com", "workspace_id": workspace_id},
    )
    assert response.status_code == 401


async def test_document_status_starts_as_pending(client):
    token, workspace_id = await register_and_login(client, "proc8@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"