async def test_register_creates_user(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "pytestuser@test.com",
            "password": "testpassword123",
            "full_name": "Pytest User",
            "workspace_name": "Pytest Workspace",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "pytestuser@test.com"
    assert "password" not in data
    assert "hashed_password" not in data


async def test_register_duplicate_email_fails(client):
    payload = {
        "email": "dupe@test.com",
        "password": "testpassword123",
        "full_name": "Dupe User",
        "workspace_name": "Dupe Workspace",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 400


async def test_login_with_correct_credentials(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "loginuser@test.com",
            "password": "testpassword123",
            "full_name": "Login User",
            "workspace_name": "Login Workspace",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "loginuser@test.com", "password": "testpassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_with_wrong_password_fails(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpass@test.com",
            "password": "testpassword123",
            "full_name": "Wrong Pass",
            "workspace_name": "Wrong Pass Workspace",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@test.com", "password": "incorrectpassword"},
    )
    assert response.status_code == 401

async def test_login_returns_bearer_token_type(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tokentype@test.com",
            "password": "testpassword123",
            "full_name": "Token Type",
            "workspace_name": "Token Workspace",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "tokentype@test.com", "password": "testpassword123"},
    )
    assert response.json()["token_type"] == "bearer"


async def test_register_missing_workspace_name_fails(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "noworkspace@test.com",
            "password": "testpassword123",
        },
    )
  

async def test_register_short_password_fails(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "shortpass@test.com",
            "password": "123",
            "workspace_name": "Test",
        },
    )
    assert response.status_code == 422


async def test_login_nonexistent_email_fails(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@test.com", "password": "testpassword123"},
    )
    assert response.status_code == 401


async def test_protected_route_without_token_fails(client):
    response = await client.get("/api/v1/usage/00000000-0000-0000-0000-000000000000/stats")
    assert response.status_code == 401


async def test_protected_route_with_invalid_token_fails(client):
    client.headers.update({"Authorization": "Bearer invalidtoken"})
    response = await client.get("/api/v1/usage/00000000-0000-0000-0000-000000000000/stats")
    assert response.status_code == 401