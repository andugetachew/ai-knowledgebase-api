import json

import httpx
import pytest_asyncio
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from app.main import app


async def register_and_login(client, email: str) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpassword123",
            "full_name": "WS User",
            "workspace_name": "WS Workspace",
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


@pytest_asyncio.fixture
async def ws_transport():
    # Cheap, stateless - safe to construct once per test without managing
    # any async context here. The actual AsyncClient/aconnect_ws lifecycle
    # is opened and closed entirely within each test body below, so there's
    # no fixture-teardown boundary for anyio's cancel scope to cross.
    return ASGIWebSocketTransport(app=app)


async def test_websocket_rejects_missing_token(client, ws_transport):
    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(
            "ws://test/api/v1/ws/chat/00000000-0000-0000-0000-000000000000",
            ac,
        ) as ws:
            await ws.send_text(json.dumps({}))
            msg = json.loads(await ws.receive_text())
            assert "error" in msg
            assert "token" in msg["error"].lower()


async def test_websocket_rejects_invalid_token(client, ws_transport):
    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(
            "ws://test/api/v1/ws/chat/00000000-0000-0000-0000-000000000000",
            ac,
        ) as ws:
            await ws.send_text(json.dumps({"token": "badtoken"}))
            msg = json.loads(await ws.receive_text())
            assert "error" in msg


async def test_websocket_rejects_wrong_workspace(client, ws_transport):
    token, _ = await register_and_login(client, "ws1@test.com")
    fake_id = "00000000-0000-0000-0000-000000000000"

    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(
            f"ws://test/api/v1/ws/chat/{fake_id}",
            ac,
        ) as ws:
            await ws.send_text(json.dumps({"token": token}))
            msg = json.loads(await ws.receive_text())
            assert "error" in msg


async def test_websocket_connects_successfully(client, ws_transport):
    token, workspace_id = await register_and_login(client, "ws2@test.com")

    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(
            f"ws://test/api/v1/ws/chat/{workspace_id}",
            ac,
        ) as ws:
            await ws.send_text(json.dumps({"token": token}))
            msg = json.loads(await ws.receive_text())
            assert msg["status"] == "connected"
            assert msg["workspace_id"] == workspace_id