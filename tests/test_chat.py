import io
from unittest.mock import AsyncMock, patch


# ── helpers ──────────────────────────────────────────────────────────────────

async def register_and_login(client, email: str) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "full_name": "Chat User",
            "workspace_name": "Chat Workspace",
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


async def upload_txt(client, workspace_id: str, headers: dict, content: str = "The capital of France is Paris.") -> dict:
    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": ("test.txt", io.BytesIO(content.encode()), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


MOCK_LLM_RESPONSE = {
    "answer": "The capital of France is Paris.",
    "sources": ["some-document-id"],
    "tokens_used": 42,
}


# ── chat tests ────────────────────────────────────────────────────────────────

async def test_chat_returns_answer(client):
    token, workspace_id = await register_and_login(client, "chat1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    await upload_txt(client, workspace_id, headers)

    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE

        response = await client.post(
            "/api/v1/chat/",
            json={"question": "What is the capital of France?", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "The capital of France is Paris."
    assert "sources" in data
    assert "tokens_used" in data


async def test_chat_response_schema(client):
    token, workspace_id = await register_and_login(client, "chat2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE

        response = await client.post(
            "/api/v1/chat/",
            json={"question": "Any question", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["answer"], str)
    assert isinstance(data["sources"], list)
    assert isinstance(data["tokens_used"], int)
    assert "conversation_id" in data
    assert isinstance(data["conversation_id"], str)


async def test_chat_without_token_fails(client):
    token, workspace_id = await register_and_login(client, "chat3@test.com")

    response = await client.post(
        "/api/v1/chat/",
        json={"question": "What is the capital of France?", "workspace_id": workspace_id},
    )
    assert response.status_code == 401


async def test_chat_with_invalid_token_fails(client):
    token, workspace_id = await register_and_login(client, "chat4@test.com")

    response = await client.post(
        "/api/v1/chat/",
        json={"question": "What is the capital of France?", "workspace_id": workspace_id},
        headers={"Authorization": "Bearer invalidtoken"},
    )
    assert response.status_code == 401


async def test_chat_nonexistent_workspace_fails(client):
    token, workspace_id = await register_and_login(client, "chat5@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE

        response = await client.post(
            "/api/v1/chat/",
            json={"question": "Any question", "workspace_id": fake_id},
            headers=headers,
        )

    assert response.status_code == 404


async def test_chat_another_users_workspace_fails(client):
    token1, workspace_id = await register_and_login(client, "chat6@test.com")

    reg2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "chat6b@test.com",
            "password": "testpassword123",
            "full_name": "Intruder",
            "workspace_name": "Intruder WS",
        },
    )
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "chat6b@test.com", "password": "testpassword123"},
    )
    intruder_token = login2.json()["access_token"]
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE

        response = await client.post(
            "/api/v1/chat/",
            json={"question": "Any question", "workspace_id": workspace_id},
            headers=intruder_headers,
        )

    assert response.status_code == 403


async def test_chat_empty_knowledge_base_returns_answer(client):
    """Chat should still work even with no documents — LLM handles it."""
    token, workspace_id = await register_and_login(client, "chat7@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    no_docs_response = {
        "answer": "No relevant documents found to answer your question.",
        "sources": [],
        "tokens_used": 0,
    }

    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = no_docs_response

        response = await client.post(
            "/api/v1/chat/",
            json={"question": "What is the capital of France?", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["sources"] == []


async def test_chat_saves_message_to_mongo(client):
    """Verify chat messages are persisted to MongoDB."""
    token, workspace_id = await register_and_login(client, "chat8@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE

        response = await client.post(
            "/api/v1/chat/",
            json={"question": "Test question", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 200

    # verify saved in mongo
    from app.db.mongodb import get_mongo_db
    mongo_db = get_mongo_db()
    saved = await mongo_db["chat_messages"].find_one({"workspace_id": workspace_id})
    assert saved is not None
    assert saved["question"] == "Test question"
    assert saved["answer"] == MOCK_LLM_RESPONSE["answer"]