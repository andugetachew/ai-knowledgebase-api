# ── helpers ──────────────────────────────────────────────────────────────────

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


# ── list workspaces ───────────────────────────────────────────────────────────

async def test_list_my_workspaces(client):
    token, workspace_id = await register_and_login(client, "ws1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/workspaces/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(w["id"] == workspace_id for w in data)


async def test_list_workspaces_without_token_fails(client):
    response = await client.get("/api/v1/workspaces/")
    assert response.status_code == 401


# ── list members ──────────────────────────────────────────────────────────────

async def test_list_members_empty(client):
    token, workspace_id = await register_and_login(client, "ws2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_list_members_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "ws3@test.com")
    response = await client.get(f"/api/v1/workspaces/{workspace_id}/members")
    assert response.status_code == 401


# ── invite member ─────────────────────────────────────────────────────────────

async def test_invite_member_success(client):
    owner_token, workspace_id = await register_and_login(client, "ws4@test.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # register second user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ws4b@test.com",
            "password": "testpassword123",
            "full_name": "Invited User",
            "workspace_name": "Invited Workspace",
        },
    )

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws4b@test.com", "role": "viewer"},
        headers=owner_headers,
    )
    assert response.status_code == 201
    assert "added" in response.json()["message"]


async def test_invite_nonexistent_user_fails(client):
    token, workspace_id = await register_and_login(client, "ws5@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ghost@test.com", "role": "viewer"},
        headers=headers,
    )
    assert response.status_code == 404


async def test_invite_duplicate_member_fails(client):
    token, workspace_id = await register_and_login(client, "ws6@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ws6b@test.com",
            "password": "testpassword123",
            "full_name": "Member",
            "workspace_name": "Member WS",
        },
    )

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws6b@test.com", "role": "viewer"},
        headers=headers,
    )

    # invite again
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws6b@test.com", "role": "editor"},
        headers=headers,
    )
    assert response.status_code == 400


async def test_invite_yourself_fails(client):
    token, workspace_id = await register_and_login(client, "ws7@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws7@test.com", "role": "viewer"},
        headers=headers,
    )
    assert response.status_code == 400


async def test_invite_without_token_fails(client):
    _, workspace_id = await register_and_login(client, "ws8@test.com")

    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "anyone@test.com", "role": "viewer"},
    )
    assert response.status_code == 401


async def test_viewer_cannot_invite(client):
    owner_token, workspace_id = await register_and_login(client, "ws9@test.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # register viewer and third user
    await client.post(
        "/api/v1/auth/register",
        json={"email": "ws9b@test.com", "password": "testpassword123",
              "full_name": "Viewer", "workspace_name": "Viewer WS"},
    )
    await client.post(
        "/api/v1/auth/register",
        json={"email": "ws9c@test.com", "password": "testpassword123",
              "full_name": "Third", "workspace_name": "Third WS"},
    )

    # invite ws9b as viewer
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws9b@test.com", "role": "viewer"},
        headers=owner_headers,
    )

    # login as viewer
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ws9b@test.com", "password": "testpassword123"},
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # viewer tries to invite ws9c
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws9c@test.com", "role": "viewer"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


# ── update role ───────────────────────────────────────────────────────────────

async def test_owner_can_update_member_role(client):
    owner_token, workspace_id = await register_and_login(client, "ws10@test.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "ws10b@test.com", "password": "testpassword123",
              "full_name": "Member", "workspace_name": "Member WS"},
    )
    member_user_id = reg.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws10b@test.com", "role": "viewer"},
        headers=owner_headers,
    )

    response = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{member_user_id}",
        json={"role": "editor"},
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert "editor" in response.json()["message"]


async def test_non_owner_cannot_update_role(client):
    owner_token, workspace_id = await register_and_login(client, "ws11@test.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    reg2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "ws11b@test.com", "password": "testpassword123",
              "full_name": "Editor", "workspace_name": "Editor WS"},
    )
    reg3 = await client.post(
        "/api/v1/auth/register",
        json={"email": "ws11c@test.com", "password": "testpassword123",
              "full_name": "Viewer", "workspace_name": "Viewer WS"},
    )
    viewer_id = reg3.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws11b@test.com", "role": "editor"},
        headers=owner_headers,
    )
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws11c@test.com", "role": "viewer"},
        headers=owner_headers,
    )

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ws11b@test.com", "password": "testpassword123"},
    )
    editor_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{viewer_id}",
        json={"role": "editor"},
        headers=editor_headers,
    )
    assert response.status_code == 403


# ── remove member ─────────────────────────────────────────────────────────────

async def test_owner_can_remove_member(client):
    owner_token, workspace_id = await register_and_login(client, "ws12@test.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "ws12b@test.com", "password": "testpassword123",
              "full_name": "Member", "workspace_name": "Member WS"},
    )
    member_id = reg.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws12b@test.com", "role": "viewer"},
        headers=owner_headers,
    )

    response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        headers=owner_headers,
    )
    assert response.status_code == 204


async def test_member_can_remove_themselves(client):
    owner_token, workspace_id = await register_and_login(client, "ws13@test.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "ws13b@test.com", "password": "testpassword123",
              "full_name": "Member", "workspace_name": "Member WS"},
    )
    member_id = reg.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws13b@test.com", "role": "viewer"},
        headers=owner_headers,
    )

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ws13b@test.com", "password": "testpassword123"},
    )
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        headers=member_headers,
    )
    assert response.status_code == 204


async def test_member_cannot_remove_others(client):
    owner_token, workspace_id = await register_and_login(client, "ws14@test.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    reg2 = await client.post(
        "/api/v1/auth/register",
        json={"email": "ws14b@test.com", "password": "testpassword123",
              "full_name": "Member2", "workspace_name": "M2 WS"},
    )
    reg3 = await client.post(
        "/api/v1/auth/register",
        json={"email": "ws14c@test.com", "password": "testpassword123",
              "full_name": "Member3", "workspace_name": "M3 WS"},
    )
    member3_id = reg3.json()["id"]

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws14b@test.com", "role": "editor"},
        headers=owner_headers,
    )
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws14c@test.com", "role": "viewer"},
        headers=owner_headers,
    )

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ws14b@test.com", "password": "testpassword123"},
    )
    editor_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{member3_id}",
        headers=editor_headers,
    )
    assert response.status_code == 403


async def test_member_can_see_workspace_in_list(client):
    owner_token, workspace_id = await register_and_login(client, "ws15@test.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    await client.post(
        "/api/v1/auth/register",
        json={"email": "ws15b@test.com", "password": "testpassword123",
              "full_name": "Member", "workspace_name": "Member WS"},
    )

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "ws15b@test.com", "role": "viewer"},
        headers=owner_headers,
    )

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ws15b@test.com", "password": "testpassword123"},
    )
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get("/api/v1/workspaces/", headers=member_headers)
    assert response.status_code == 200
    workspace_ids = [w["id"] for w in response.json()]
    assert workspace_id in workspace_ids