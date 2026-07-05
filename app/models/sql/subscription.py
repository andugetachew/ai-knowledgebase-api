import uuid
from datetime import datetime, UTC
from enum import Enum as PyEnum
from sqlalchemy import ForeignKey, Integer, Enum, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class PlanType(str, PyEnum):
    free = "free"
    pro = "pro"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), unique=True, nullable=False)
    plan: Mapped[PlanType] = mapped_column(Enum(PlanType), default=PlanType.free, nullable=False)
    queries_per_day: Mapped[int] = mapped_column(Integer, default=10)
    stripe_customer_id: Mapped[str] = mapped_column(String, nullable=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC))

    workspace = relationship("Workspace", back_populates="subscription")