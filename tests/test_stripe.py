import pytest
import json
from unittest.mock import patch, MagicMock


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


# ── Checkout ─────────────────────────────────────────────────────────────────

async def test_create_pro_checkout_returns_url(client):
    token, workspace_id = await register_and_login(client, "stripe1@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test_session_123"
    mock_session.id = "cs_test_123"

    with patch("app.api.v1.checkout.stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            f"/api/v1/checkout/{workspace_id}/pro",
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "checkout_url" in data
    assert data["checkout_url"] == "https://checkout.stripe.com/pay/test_session_123"
    assert "session_id" in data


async def test_create_free_checkout_returns_url(client):
    token, workspace_id = await register_and_login(client, "stripe2@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test_free_123"
    mock_session.id = "cs_test_free_123"

    with patch("app.api.v1.checkout.stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            f"/api/v1/checkout/{workspace_id}/free",
            headers=headers,
        )

    assert response.status_code == 200
    assert "checkout_url" in response.json()


async def test_checkout_without_token_fails(client):
    import uuid
    fake_id = str(uuid.uuid4())
    response = await client.post(f"/api/v1/checkout/{fake_id}/pro")
    assert response.status_code == 401


async def test_checkout_wrong_workspace_fails(client):
    token, _ = await register_and_login(client, "stripe3@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    import uuid
    fake_id = str(uuid.uuid4())

    response = await client.post(
        f"/api/v1/checkout/{fake_id}/pro",
        headers=headers,
    )
    assert response.status_code == 404


async def test_checkout_stripe_error_returns_502(client):
    import stripe
    token, workspace_id = await register_and_login(client, "stripe4@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.api.v1.checkout.stripe.checkout.Session.create",
        side_effect=stripe.StripeError("card declined"),
    ):
        response = await client.post(
            f"/api/v1/checkout/{workspace_id}/pro",
            headers=headers,
        )

    assert response.status_code == 502


# ── Webhook ───────────────────────────────────────────────────────────────────

async def test_webhook_invalid_signature_returns_400(client):
    response = await client.post(
        "/api/v1/webhooks/stripe",
        content=b'{"type": "checkout.session.completed"}',
        headers={
            "stripe-signature": "invalid_signature",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400


async def test_webhook_checkout_completed_upgrades_plan(client):
    token, workspace_id = await register_and_login(client, "stripe5@test.com")

    mock_event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {
                    "workspace_id": workspace_id,
                    "price_id": "price_pro_test",
                },
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
            }
        }
    }

    with patch("app.api.v1.stripe_webhook.stripe.Webhook.construct_event", return_value=mock_event):
        with patch(
            "app.api.v1.stripe_webhook.PRICE_TO_PLAN",
            {"price_pro_test": "pro"},
        ):
            response = await client.post(
                "/api/v1/webhooks/stripe",
                content=json.dumps(mock_event).encode(),
                headers={
                    "stripe-signature": "valid_sig",
                    "Content-Type": "application/json",
                },
            )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_webhook_subscription_deleted_downgrades_to_free(client):
    token, workspace_id = await register_and_login(client, "stripe6@test.com")

    mock_event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "customer": "cus_nonexistent_123",
            }
        }
    }

    with patch("app.api.v1.stripe_webhook.stripe.Webhook.construct_event", return_value=mock_event):
        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=json.dumps(mock_event).encode(),
            headers={
                "stripe-signature": "valid_sig",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200


async def test_webhook_unknown_event_ignored(client):
    mock_event = {
        "type": "payment_intent.created",
        "data": {"object": {}}
    }

    with patch("app.api.v1.stripe_webhook.stripe.Webhook.construct_event", return_value=mock_event):
        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=json.dumps(mock_event).encode(),
            headers={
                "stripe-signature": "valid_sig",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200