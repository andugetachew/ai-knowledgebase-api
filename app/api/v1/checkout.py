import stripe
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_workspace_access
from app.core.config import settings
from app.db.postgres import get_db
from app.models.sql.user import User
from app.models.sql.workspace_member import MemberRole

router = APIRouter(prefix="/api/v1/checkout", tags=["checkout"])

stripe.api_key = settings.stripe_secret_key


@router.post("/{workspace_id}/pro")
async def create_pro_checkout(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout session to upgrade to Pro."""
    await get_workspace_access(workspace_id, current_user, db, min_role=MemberRole.owner)

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": settings.stripe_pro_price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url="https://ai-knowledgebase-api-m9ry.onrender.com/docs#/subscription",
            cancel_url="https://ai-knowledgebase-api-m9ry.onrender.com/docs",
            metadata={
                "workspace_id": str(workspace_id),
                "price_id": settings.stripe_pro_price_id,
            },
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {str(e)}",
        )


@router.post("/{workspace_id}/free")
async def downgrade_to_free(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Downgrade workspace to free plan via Stripe."""
    await get_workspace_access(workspace_id, current_user, db, min_role=MemberRole.owner)

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": settings.stripe_free_price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url="https://ai-knowledgebase-api-m9ry.onrender.com/docs#/subscription",
            cancel_url="https://ai-knowledgebase-api-m9ry.onrender.com/docs",
            metadata={
                "workspace_id": str(workspace_id),
                "price_id": settings.stripe_free_price_id,
            },
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except stripe.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {str(e)}",
        )