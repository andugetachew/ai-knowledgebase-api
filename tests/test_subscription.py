async def register_and_login(client, email: str) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "full_name": "Sub User",
            "workspace_name": "Sub Workspace",
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


# ── get subscription ──────────────────────────────────────────────────────────

async def test_get_subscription_default_plan(client):
    token, workspace_id = await register_and_login(client, "sub1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/subscription/{workspace_id}", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_id"] == workspace_id
    assert data["plan"] == "free"
    assert data["queries_used_today"] == 0
    assert data["queries_remaining"] == data["queries_per_day"]


async def test_get_subscription_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "sub2@test.com")
    response = await client.get(f"/api/v1/subscription/{workspace_id}")
    assert response.status_code == 401


async def test_get_subscription_workspace_not_found(client):
    token, _ = await register_and_login(client, "sub3@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/subscription/{fake_id}", headers=headers
    )
    assert response.status_code == 404


async def test_get_subscription_other_users_workspace_fails(client):
    _, workspace_id = await register_and_login(client, "sub4@test.com")
    intruder_token, _ = await register_and_login(client, "sub4b@test.com")
    headers = {"Authorization": f"Bearer {intruder_token}"}

    response = await client.get(
        f"/api/v1/subscription/{workspace_id}", headers=headers
    )
    assert response.status_code == 404


# ── upgrade subscription ──────────────────────────────────────────────────────

async def test_upgrade_to_pro(client):
    token, workspace_id = await register_and_login(client, "sub5@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        f"/api/v1/subscription/{workspace_id}",
        json={"plan": "pro"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "pro"
    assert data["queries_per_day"] == 10000


async def test_downgrade_to_free(client):
    token, workspace_id = await register_and_login(client, "sub6@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    await client.patch(
        f"/api/v1/subscription/{workspace_id}",
        json={"plan": "pro"},
        headers=headers,
    )

    response = await client.patch(
        f"/api/v1/subscription/{workspace_id}",
        json={"plan": "free"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "free"
    assert data["queries_per_day"] == 10


async def test_upgrade_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "sub7@test.com")
    response = await client.patch(
        f"/api/v1/subscription/{workspace_id}",
        json={"plan": "pro"},
    )
    assert response.status_code == 401


async def test_upgrade_workspace_not_found(client):
    token, _ = await register_and_login(client, "sub8@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.patch(
        f"/api/v1/subscription/{fake_id}",
        json={"plan": "pro"},
        headers=headers,
    )
    assert response.status_code == 404


async def test_upgrade_other_users_workspace_fails(client):
    _, workspace_id = await register_and_login(client, "sub9@test.com")
    intruder_token, _ = await register_and_login(client, "sub9b@test.com")
    headers = {"Authorization": f"Bearer {intruder_token}"}

    response = await client.patch(
        f"/api/v1/subscription/{workspace_id}",
        json={"plan": "pro"},
        headers=headers,
    )
    assert response.status_code == 404


async def test_upgrade_invalid_plan_fails(client):
    token, workspace_id = await register_and_login(client, "sub10@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        f"/api/v1/subscription/{workspace_id}",
        json={"plan": "enterprise"},
        headers=headers,
    )
    assert response.status_code == 422