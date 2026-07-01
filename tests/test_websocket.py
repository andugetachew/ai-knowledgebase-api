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

class FakeStreamResponse:
    def __init__(self, lines):
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class FakeStreamContextManager:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return FakeStreamResponse(self._lines)

    async def __aexit__(self, *args):
        return False


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, method, url, headers=None, json=None):
        import json as json_module
        sse_lines = [
            "data: " + json_module.dumps({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}}),
            "data: " + json_module.dumps({"type": "content_block_delta", "delta": {"type": "text_delta", "text": " world"}}),
            "data: " + json_module.dumps({"type": "message_delta", "usage": {"output_tokens": 42}}),
            "data: " + json_module.dumps({"type": "message_stop"}),
            "data: [DONE]",
        ]
        return FakeStreamContextManager(sse_lines)


class FakeAsyncClientWithBlankLines(FakeAsyncClient):
    def stream(self, method, url, headers=None, json=None):
        import json as json_module
        sse_lines = [
            "",  # blank keep-alive line — hits the `continue` branch
            "not-json-after-prefix",  # doesn't start with "data: " either, also hits continue
            "data: " + "{not valid json",  # hits JSONDecodeError branch
            "data: " + json_module.dumps({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}}),
            "data: " + json_module.dumps({"type": "message_delta", "usage": {"output_tokens": 5}}),
            "data: " + json_module.dumps({"type": "message_stop"}),
            "data: [DONE]",
        ]
        return FakeStreamContextManager(sse_lines)


async def test_websocket_empty_question(client, ws_transport):
    token, workspace_id = await register_and_login(client, "ws4@test.com")

    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(f"ws://test/api/v1/ws/chat/{workspace_id}", ac) as ws:
            await ws.send_text(json.dumps({"token": token}))
            await ws.receive_text()  # connected

            await ws.send_text(json.dumps({"question": "   "}))
            msg = json.loads(await ws.receive_text())
            assert msg["error"] == "Empty question"


async def test_websocket_full_chat_flow(client, ws_transport, monkeypatch):
    import app.api.v1.websocket as ws_module

    async def fake_retrieve(query, workspace_id, db):
        return [{"document_id": "doc-1", "content": "Some relevant content"}]

    monkeypatch.setattr(ws_module, "retrieve_relevant_chunks", fake_retrieve)

    token, workspace_id = await register_and_login(client, "ws3@test.com")

    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(f"ws://test/api/v1/ws/chat/{workspace_id}", ac) as ws:
            await ws.send_text(json.dumps({"token": token}))
            await ws.receive_text()  # connected

            # Patch only now — after the real WS handshake completes,
            # so it doesn't break aconnect_ws's own use of httpx.AsyncClient.
            monkeypatch.setattr(ws_module.httpx, "AsyncClient", FakeAsyncClient)

            await ws.send_text(json.dumps({"question": "What is this about?"}))

            tokens = []
            done_msg = None
            while True:
                msg = json.loads(await ws.receive_text())
                if msg.get("type") == "token":
                    tokens.append(msg["content"])
                elif msg.get("type") == "done":
                    done_msg = msg
                    break

            assert "".join(tokens) == "Hello world"
            assert done_msg["tokens_used"] == 42
            assert done_msg["sources"] == ["doc-1"]


async def test_websocket_no_relevant_chunks(client, ws_transport, monkeypatch):
    import app.api.v1.websocket as ws_module

    async def fake_retrieve_empty(query, workspace_id, db):
        return []

    monkeypatch.setattr(ws_module, "retrieve_relevant_chunks", fake_retrieve_empty)

    token, workspace_id = await register_and_login(client, "ws5@test.com")

    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(f"ws://test/api/v1/ws/chat/{workspace_id}", ac) as ws:
            await ws.send_text(json.dumps({"token": token}))
            await ws.receive_text()  # connected

            monkeypatch.setattr(ws_module.httpx, "AsyncClient", FakeAsyncClient)

            await ws.send_text(json.dumps({"question": "Anything in here?"}))

            done_msg = None
            while True:
                msg = json.loads(await ws.receive_text())
                if msg.get("type") == "done":
                    done_msg = msg
                    break

            assert done_msg["sources"] == []


async def test_websocket_handles_internal_error(client, ws_transport, monkeypatch):
    import app.api.v1.websocket as ws_module

    async def fake_retrieve_raises(query, workspace_id, db):
        raise RuntimeError("boom")

    monkeypatch.setattr(ws_module, "retrieve_relevant_chunks", fake_retrieve_raises)

    token, workspace_id = await register_and_login(client, "ws6@test.com")

    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(f"ws://test/api/v1/ws/chat/{workspace_id}", ac) as ws:
            await ws.send_text(json.dumps({"token": token}))
            await ws.receive_text()

            await ws.send_text(json.dumps({"question": "trigger error"}))
            msg = json.loads(await ws.receive_text())
            assert "boom" in msg["error"]


async def test_websocket_handles_malformed_sse_lines(client, ws_transport, monkeypatch):
    import app.api.v1.websocket as ws_module

    async def fake_retrieve(query, workspace_id, db):
        return []

    monkeypatch.setattr(ws_module, "retrieve_relevant_chunks", fake_retrieve)

    token, workspace_id = await register_and_login(client, "ws7@test.com")

    async with httpx.AsyncClient(transport=ws_transport, base_url="ws://test") as ac:
        async with aconnect_ws(f"ws://test/api/v1/ws/chat/{workspace_id}", ac) as ws:
            await ws.send_text(json.dumps({"token": token}))
            await ws.receive_text()  # connected

            monkeypatch.setattr(ws_module.httpx, "AsyncClient", FakeAsyncClientWithBlankLines)

            await ws.send_text(json.dumps({"question": "test"}))

            done_msg = None
            while True:
                msg = json.loads(await ws.receive_text())
                if msg.get("type") == "done":
                    done_msg = msg
                    break

            assert done_msg["tokens_used"] == 5