import secrets
from datetime import datetime, UTC, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db.postgres import get_db
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.models.sql.subscription import Subscription, PlanType
from app.schemas.auth import Token, UserLogin, UserRegister
from app.schemas.user import UserOut
from app.services.email_service import send_password_reset_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# In-memory token store — fine for dev/portfolio
# Production would use Redis with TTL
_reset_tokens: dict[str, dict] = {}


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.flush()

    workspace = Workspace(
        name=payload.workspace_name,
        owner_id=user.id,
        api_key=secrets.token_urlsafe(32),
    )
    db.add(workspace)
    await db.flush()

    subscription = Subscription(
        workspace_id=workspace.id,
        plan=PlanType.free,
        queries_per_day=10,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(user)
    await db.refresh(workspace)
    user.workspace_id = workspace.id
    return user


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token)


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset email.
    Always returns 200 even if email not found — prevents user enumeration.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(32)
        _reset_tokens[token] = {
            "user_id": str(user.id),
            "email": user.email,
            "expires_at": datetime.now(UTC) + timedelta(hours=1),
        }
        try:
            await send_password_reset_email(user.email, token)
        except Exception:
            # Don't leak email errors to client
            pass

    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset using token from email."""
    token_data = _reset_tokens.get(payload.token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    if datetime.now(UTC) > token_data["expires_at"]:
        _reset_tokens.pop(payload.token, None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one.",
        )

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )

    result = await db.execute(
        select(User).where(User.id == token_data["user_id"])
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found.",
        )

    user.hashed_password = hash_password(payload.new_password)
    await db.commit()

    # Invalidate token after use
    _reset_tokens.pop(payload.token, None)

    return {"message": "Password reset successfully. You can now log in."}