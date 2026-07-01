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


async def test_queries_over_time_empty(client):
    token, workspace_id = await register_and_login(client, "analytics1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/queries-over-time",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "buckets" in data
    assert data["workspace_id"] == workspace_id
    assert data["period"] == "7d"


async def test_queries_over_time_with_period(client):
    token, workspace_id = await register_and_login(client, "analytics2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/queries-over-time?period=24h",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "24h"
    assert data["granularity"] == "hour"


async def test_queries_over_time_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "analytics3@test.com")
    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/queries-over-time"
    )
    assert response.status_code == 401


async def test_queries_over_time_wrong_workspace_fails(client):
    token, _ = await register_and_login(client, "analytics4@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/analytics/{fake_id}/queries-over-time",
        headers=headers,
    )
    assert response.status_code == 404


async def test_top_documents_empty(client):
    token, workspace_id = await register_and_login(client, "analytics5@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/top-documents",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "top_documents" in data
    assert data["workspace_id"] == workspace_id


async def test_top_documents_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "analytics6@test.com")
    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/top-documents"
    )
    assert response.status_code == 401


async def test_performance_metrics_empty(client):
    token, workspace_id = await register_and_login(client, "analytics7@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/performance",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_queries" in data
    assert "avg_tokens_per_query" in data
    assert "total_tokens" in data
    assert data["total_queries"] == 0


async def test_performance_metrics_with_period(client):
    token, workspace_id = await register_and_login(client, "analytics8@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/performance?period=30d",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["period"] == "30d"


async def test_performance_metrics_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "analytics9@test.com")
    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/performance"
    )
    assert response.status_code == 401


async def test_live_activity_returns_data(client):
    token, workspace_id = await register_and_login(client, "analytics10@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/live",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "active_queries_last_hour" in data
    assert "workspace_id" in data


async def test_live_activity_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "analytics11@test.com")
    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/live"
    )
    assert response.status_code == 401


from datetime import datetime, UTC
from app.db.mongodb import get_mongo_db

async def test_performance_metrics_with_data(client):
    token, workspace_id = await register_and_login(client, "analytics12@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    mongo_db = get_mongo_db()
    await mongo_db["chat_messages"].insert_many([
        {"workspace_id": workspace_id, "created_at": datetime.now(UTC), "tokens_used": 100, "sources": ["doc1"]},
        {"workspace_id": workspace_id, "created_at": datetime.now(UTC), "tokens_used": 200, "sources": ["doc1", "doc2"]},
    ])

    response = await client.get(
        f"/api/v1/analytics/{workspace_id}/performance", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_queries"] == 2
    assert data["total_tokens"] == 300
    assert data["avg_tokens_per_query"] == 150.0

    await mongo_db["chat_messages"].delete_many({"workspace_id": workspace_id})


async def test_analytics_stream_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "analytics14@test.com")
    response = await client.get(f"/api/v1/analytics/{workspace_id}/stream")
    assert response.status_code == 401