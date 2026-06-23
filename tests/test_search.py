import io
from unittest.mock import patch


# ── helpers ──────────────────────────────────────────────────────────────────

async def register_and_login(client, email: str) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "full_name": "Search User",
            "workspace_name": "Search Workspace",
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


async def upload_txt(client, workspace_id: str, headers: dict, content: str) -> dict:
    response = await client.post(
        f"/api/v1/documents/?workspace_id={workspace_id}",
        files={"file": ("test.txt", io.BytesIO(content.encode()), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


MOCK_EMBEDDING = [0.1] * 384  # all-MiniLM-L6-v2 produces 384-dim vectors


# ── search tests ──────────────────────────────────────────────────────────────

async def test_search_returns_results(client):
    token, workspace_id = await register_and_login(client, "search1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.search.generate_embedding", return_value=MOCK_EMBEDDING):
        # seed a chunk directly into mongo
        from app.db.mongodb import get_mongo_db
        mongo_db = get_mongo_db()
        await mongo_db["chunks"].insert_one({
            "document_id": "doc-123",
            "workspace_id": workspace_id,
            "content": "Paris is the capital of France.",
            "chunk_index": 0,
            "embedding": MOCK_EMBEDDING,
        })

        response = await client.post(
            "/api/v1/search/",
            json={"query": "capital of France", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "capital of France"
    assert data["total"] >= 1
    assert len(data["results"]) >= 1


async def test_search_result_schema(client):
    token, workspace_id = await register_and_login(client, "search2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.search.generate_embedding", return_value=MOCK_EMBEDDING):
        from app.db.mongodb import get_mongo_db
        mongo_db = get_mongo_db()
        await mongo_db["chunks"].insert_one({
            "document_id": "doc-456",
            "workspace_id": workspace_id,
            "content": "FastAPI is a modern Python web framework.",
            "chunk_index": 0,
            "embedding": MOCK_EMBEDDING,
        })

        response = await client.post(
            "/api/v1/search/",
            json={"query": "Python framework", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert "document_id" in result
    assert "content" in result
    assert "chunk_index" in result
    assert "score" in result
    assert isinstance(result["score"], float)


async def test_search_empty_workspace_returns_empty(client):
    token, workspace_id = await register_and_login(client, "search3@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.search.generate_embedding", return_value=MOCK_EMBEDDING):
        response = await client.post(
            "/api/v1/search/",
            json={"query": "anything", "workspace_id": workspace_id},
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []


async def test_search_respects_top_k(client):
    token, workspace_id = await register_and_login(client, "search4@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.v1.search.generate_embedding", return_value=MOCK_EMBEDDING):
        from app.db.mongodb import get_mongo_db
        mongo_db = get_mongo_db()
        await mongo_db["chunks"].insert_many([
            {
                "document_id": f"doc-{i}",
                "workspace_id": workspace_id,
                "content": f"Chunk number {i}",
                "chunk_index": i,
                "embedding": MOCK_EMBEDDING,
            }
            for i in range(10)
        ])

        response = await client.post(
            "/api/v1/search/",
            json={"query": "chunk", "workspace_id": workspace_id, "top_k": 3},
            headers=headers,
        )

    assert response.status_code == 200
    assert len(response.json()["results"]) == 3


async def test_search_without_token_fails(client):
    response = await client.post(
        "/api/v1/search/",
        json={"query": "anything", "workspace_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


async def test_search_invalid_token_fails(client):
    response = await client.post(
        "/api/v1/search/",
        json={"query": "anything", "workspace_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": "Bearer badtoken"},
    )
    assert response.status_code == 401


async def test_search_nonexistent_workspace_fails(client):
    token, _ = await register_and_login(client, "search5@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    with patch("app.api.v1.search.generate_embedding", return_value=MOCK_EMBEDDING):
        response = await client.post(
            "/api/v1/search/",
            json={"query": "anything", "workspace_id": fake_id},
            headers=headers,
        )

    assert response.status_code == 404


async def test_search_another_users_workspace_fails(client):
    token1, workspace_id = await register_and_login(client, "search6@test.com")

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "search6b@test.com",
            "password": "testpassword123",
            "full_name": "Intruder",
            "workspace_name": "Intruder WS",
        },
    )
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "search6b@test.com", "password": "testpassword123"},
    )
    intruder_token = login2.json()["access_token"]

    with patch("app.api.v1.search.generate_embedding", return_value=MOCK_EMBEDDING):
        response = await client.post(
            "/api/v1/search/",
            json={"query": "anything", "workspace_id": workspace_id},
            headers={"Authorization": f"Bearer {intruder_token}"},
        )

    assert response.status_code == 404