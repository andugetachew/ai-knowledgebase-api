from unittest.mock import AsyncMock, patch

MOCK_LLM_RESPONSE = {
    "answer": "Paris is the capital of France.",
    "sources": ["doc-123"],
    "tokens_used": 50,
}


async def register_and_login(client, email: str) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "full_name": "Usage User",
            "workspace_name": "Usage Workspace",
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


# ── stats tests ───────────────────────────────────────────────────────────────

async def test_stats_empty_workspace(client):
    token, workspace_id = await register_and_login(client, "usage1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/usage/{workspace_id}/stats",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_id"] == workspace_id
    assert data["total_documents"] == 0
    assert data["total_chunks"] == 0
    assert data["total_queries"] == 0
    assert data["total_tokens_used"] == 0


async def test_stats_after_queries(client):
    token, workspace_id = await register_and_login(client, "usage2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    # make two chat queries
    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE
        for _ in range(2):
            await client.post(
                "/api/v1/chat/",
                json={"question": "What is the capital of France?", "workspace_id": workspace_id},
                headers=headers,
            )

    response = await client.get(
        f"/api/v1/usage/{workspace_id}/stats",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_queries"] == 2
    assert data["total_tokens_used"] == 100  # 50 tokens x 2


async def test_stats_schema(client):
    token, workspace_id = await register_and_login(client, "usage3@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/usage/{workspace_id}/stats",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "workspace_id" in data
    assert "total_documents" in data
    assert "total_chunks" in data
    assert "total_queries" in data
    assert "total_tokens_used" in data


async def test_stats_nonexistent_workspace_fails(client):
    token, _ = await register_and_login(client, "usage4@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/usage/{fake_id}/stats",
        headers=headers,
    )
    assert response.status_code == 404


async def test_stats_another_users_workspace_fails(client):
    token1, workspace_id = await register_and_login(client, "usage5@test.com")

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "usage5b@test.com",
            "password": "testpassword123",
            "full_name": "Intruder",
            "workspace_name": "Intruder WS",
        },
    )
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "usage5b@test.com", "password": "testpassword123"},
    )
    intruder_headers = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    response = await client.get(
        f"/api/v1/usage/{workspace_id}/stats",
        headers=intruder_headers,
    )
    assert response.status_code == 404


async def test_stats_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "usage6@test.com")

    response = await client.get(f"/api/v1/usage/{workspace_id}/stats")
    assert response.status_code == 401


# ── history tests ─────────────────────────────────────────────────────────────

async def test_history_empty(client):
    token, workspace_id = await register_and_login(client, "usage7@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/usage/{workspace_id}/history",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_history_returns_queries(client):
    token, workspace_id = await register_and_login(client, "usage8@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE
        await client.post(
            "/api/v1/chat/",
            json={"question": "Test question", "workspace_id": workspace_id},
            headers=headers,
        )

    response = await client.get(
        f"/api/v1/usage/{workspace_id}/history",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["question"] == "Test question"
    assert data[0]["answer"] == MOCK_LLM_RESPONSE["answer"]
    assert data[0]["tokens_used"] == 50


async def test_history_schema(client):
    token, workspace_id = await register_and_login(client, "usage9@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.chat.generate_answer", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = MOCK_LLM_RESPONSE
        await client.post(
            "/api/v1/chat/",
            json={"question": "Schema test", "workspace_id": workspace_id},
            headers=headers,
        )

    response = await client.get(
        f"/api/v1/usage/{workspace_id}/history",
        headers=headers,
    )
    assert response.status_code == 200
    item = response.json()[0]
    assert "question" in item
    assert "answer" in item
    assert "sources" in item
    assert "tokens_used" in item
    assert "created_at" in item


async def test_history_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "usage10@test.com")

    response = await client.get(f"/api/v1/usage/{workspace_id}/history")
    assert response.status_code == 401


async def test_history_nonexistent_workspace_fails(client):
    token, _ = await register_and_login(client, "usage11@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/usage/{fake_id}/history",
        headers=headers,
    )
    assert response.status_code == 404