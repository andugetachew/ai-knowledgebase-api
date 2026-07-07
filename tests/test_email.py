import pytest
from unittest.mock import patch, AsyncMock


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


# ── Password Reset ────────────────────────────────────────────────────────────

async def test_forgot_password_returns_200_for_existing_email(client):
    await register_and_login(client, "reset1@test.com")

    with patch(
        "app.api.v1.auth.send_password_reset_email",
        new_callable=AsyncMock,
    ):
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset1@test.com"},
        )

    assert response.status_code == 200
    assert "reset link" in response.json()["message"]


async def test_forgot_password_returns_200_for_nonexistent_email(client):
    """Should return 200 even for unknown email to prevent user enumeration."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "doesnotexist@test.com"},
    )
    assert response.status_code == 200
    assert "reset link" in response.json()["message"]


async def test_forgot_password_sends_email(client):
    await register_and_login(client, "reset2@test.com")

    with patch(
        "app.api.v1.auth.send_password_reset_email",
        new_callable=AsyncMock,
    ) as mock_send:
        await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset2@test.com"},
        )
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == "reset2@test.com"


async def test_reset_password_with_valid_token(client):
    await register_and_login(client, "reset3@test.com")

    from app.api.v1.auth import _reset_tokens
    from datetime import datetime, UTC, timedelta
    import uuid

    token = "valid_test_token_123"
    _reset_tokens[token] = {
        "user_id": str(uuid.uuid4()),
        "email": "reset3@test.com",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }

    # get real user_id
    result = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset3@test.com", "password": "testpassword123"},
    )
    from app.core.security import decode_access_token
    user_id = decode_access_token(result.json()["access_token"])
    _reset_tokens[token]["user_id"] = user_id

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "newpassword456"},
    )
    assert response.status_code == 200
    assert "successfully" in response.json()["message"]

    # verify can login with new password
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset3@test.com", "password": "newpassword456"},
    )
    assert login.status_code == 200


async def test_reset_password_with_invalid_token(client):
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "nonexistent_token", "new_password": "newpassword456"},
    )
    assert response.status_code == 400


async def test_reset_password_with_expired_token(client):
    await register_and_login(client, "reset4@test.com")

    from app.api.v1.auth import _reset_tokens
    from datetime import datetime, UTC, timedelta

    token = "expired_token_123"
    _reset_tokens[token] = {
        "user_id": "some-user-id",
        "email": "reset4@test.com",
        "expires_at": datetime.now(UTC) - timedelta(hours=2),
    }

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "newpassword456"},
    )
    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


async def test_reset_password_short_password_fails(client):
    from app.api.v1.auth import _reset_tokens
    from datetime import datetime, UTC, timedelta

    token = "short_pw_token"
    _reset_tokens[token] = {
        "user_id": "some-user-id",
        "email": "reset5@test.com",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "short"},
    )
    assert response.status_code == 400


async def test_token_invalidated_after_use(client):
    """Token should be deleted after successful reset."""
    await register_and_login(client, "reset6@test.com")

    from app.api.v1.auth import _reset_tokens
    from datetime import datetime, UTC, timedelta
    from app.core.security import decode_access_token

    token = "one_time_token_456"
    result = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset6@test.com", "password": "testpassword123"},
    )
    user_id = decode_access_token(result.json()["access_token"])
    _reset_tokens[token] = {
        "user_id": user_id,
        "email": "reset6@test.com",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }

    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "newpassword789"},
    )

    # second use of same token should fail
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "anotherpassword"},
    )
    assert response.status_code == 400


# ── Invite Email ──────────────────────────────────────────────────────────────

async def test_invite_sends_email(client):
    token, workspace_id = await register_and_login(client, "invite_sender@test.com")
    await register_and_login(client, "invite_receiver@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.api.v1.workspace.send_workspace_invite_email",
        new_callable=AsyncMock,
    ) as mock_send:
        response = await client.post(
            f"/api/v1/workspaces/{workspace_id}/members",
            json={"email": "invite_receiver@test.com", "role": "editor"},
            headers=headers,
        )

    assert response.status_code == 201
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args
    assert call_kwargs[1]["to"] == "invite_receiver@test.com"
    assert call_kwargs[1]["role"] == "editor"


async def test_invite_succeeds_even_if_email_fails(client):
    """Email failure should not prevent the invite from being created."""
    token, workspace_id = await register_and_login(client, "invite_sender2@test.com")
    await register_and_login(client, "invite_receiver2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.api.v1.workspace.send_workspace_invite_email",
        new_callable=AsyncMock,
        side_effect=Exception("SMTP connection failed"),
    ):
        response = await client.post(
            f"/api/v1/workspaces/{workspace_id}/members",
            json={"email": "invite_receiver2@test.com", "role": "viewer"},
            headers=headers,
        )

    assert response.status_code == 201