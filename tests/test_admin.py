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


async def test_admin_dashboard_returns_stats(client):
    token, _ = await register_and_login(client, "admin1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    assert "top_workspaces" in data
    assert "token_trends" in data


async def test_admin_stats_schema(client):
    token, _ = await register_and_login(client, "admin2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert "total_users" in stats
    assert "total_workspaces" in stats
    assert "total_documents" in stats
    assert "total_queries" in stats
    assert "total_tokens_used" in stats
    assert "free_plan_workspaces" in stats
    assert "pro_plan_workspaces" in stats


async def test_admin_stats_counts_users(client):
    token, _ = await register_and_login(client, "admin3@test.com")
    await register_and_login(client, "admin3b@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert response.status_code == 200
    assert response.json()["stats"]["total_users"] >= 2


async def test_admin_dashboard_without_token_fails(client):
    response = await client.get("/api/v1/admin/dashboard")
    assert response.status_code == 401


async def test_admin_list_workspaces(client):
    token, _ = await register_and_login(client, "admin4@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/workspaces", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


async def test_admin_workspace_schema(client):
    token, _ = await register_and_login(client, "admin5@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/workspaces", headers=headers)
    assert response.status_code == 200
    ws = response.json()[0]
    assert "workspace_id" in ws
    assert "workspace_name" in ws
    assert "owner_email" in ws
    assert "plan" in ws
    assert "total_queries" in ws
    assert "total_tokens" in ws
    assert "total_documents" in ws


async def test_admin_list_users(client):
    token, _ = await register_and_login(client, "admin6@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


async def test_admin_users_schema(client):
    token, _ = await register_and_login(client, "admin7@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 200
    user = response.json()[0]
    assert "id" in user
    assert "email" in user
    assert "workspace_count" in user
    assert "is_active" in user


async def test_admin_token_trends(client):
    token, _ = await register_and_login(client, "admin8@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/stats/tokens?days=7", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_admin_token_trends_without_token_fails(client):
    response = await client.get("/api/v1/admin/stats/tokens")
    assert response.status_code == 401


async def test_admin_free_plan_count_increases_on_register(client):
    token, _ = await register_and_login(client, "admin9@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/admin/dashboard", headers=headers)
    assert response.status_code == 200
    assert response.json()["stats"]["free_plan_workspaces"] >= 1