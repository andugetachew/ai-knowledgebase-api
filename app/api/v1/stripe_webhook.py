import stripe
from fastapi import APIRouter, Request, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.postgres import get_db
from app.models.sql.subscription import Subscription
from fastapi import Depends

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
                await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        subscription_obj = event["data"]["object"]
        customer_id = subscription_obj.get("customer")

        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_customer_id == customer_id
            )
        )
        subscription = result.scalar_one_or_none()
        if subscription:
            subscription.plan = "free"
            subscription.stripe_subscription_id = None
            await db.commit()

    return {"status": "ok"}