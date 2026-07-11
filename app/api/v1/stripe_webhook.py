import stripe
import json
from datetime import datetime, UTC
from fastapi import APIRouter, Request, HTTPException, Header, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.postgres import get_db
from app.models.sql.subscription import Subscription, SubscriptionStatus

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

stripe.api_key = settings.stripe_secret_key

PRICE_TO_PLAN = {
    settings.stripe_free_price_id: "free",
    settings.stripe_pro_price_id: "pro",
}


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        workspace_id = session["metadata"].get("workspace_id")
        price_id = session["metadata"].get("price_id")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        if workspace_id and price_id:
            plan = PRICE_TO_PLAN.get(price_id, "free")

            # fetch full subscription object from Stripe to get period dates
            stripe_sub = None
            if subscription_id:
                try:
                    stripe_sub = stripe.Subscription.retrieve(subscription_id)
                except Exception:
                    pass

            result = await db.execute(
                select(Subscription).where(
                    Subscription.workspace_id == workspace_id
                )
            )
            subscription = result.scalar_one_or_none()
            if subscription:
                subscription.plan = plan
                subscription.stripe_customer_id = customer_id
                subscription.stripe_subscription_id = subscription_id
                subscription.status = SubscriptionStatus.active
                subscription.cancel_at_period_end = False
                subscription.updated_at = datetime.now(UTC)

                if stripe_sub:
                    period_end = stripe_sub.get("current_period_end")
                    if period_end:
                        subscription.current_period_end = datetime.fromtimestamp(
                            period_end, tz=UTC
                        )

                await db.commit()

    elif event["type"] == "customer.subscription.updated":
        stripe_sub = event["data"]["object"]
        customer_id = stripe_sub.get("customer")

        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_customer_id == customer_id
            )
        )
        subscription = result.scalar_one_or_none()
        if subscription:
            subscription.status = SubscriptionStatus(
                stripe_sub.get("status", "active")
            )
            subscription.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
            period_end = stripe_sub.get("current_period_end")
            if period_end:
                subscription.current_period_end = datetime.fromtimestamp(period_end, tz=UTC)
            subscription.updated_at = datetime.now(UTC)
            await db.commit()

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")

        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_customer_id == customer_id
            )
        )
        subscription = result.scalar_one_or_none()
        if subscription:
            subscription.status = SubscriptionStatus.past_due
            subscription.updated_at = datetime.now(UTC)
            await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        stripe_sub = event["data"]["object"]
        customer_id = stripe_sub.get("customer")

        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_customer_id == customer_id
            )
        )
        subscription = result.scalar_one_or_none()
        if subscription:
            subscription.plan = "free"
            subscription.status = SubscriptionStatus.canceled
            subscription.stripe_subscription_id = None
            subscription.cancel_at_period_end = False
            subscription.updated_at = datetime.now(UTC)
            await db.commit()

    return {"status": "ok"}