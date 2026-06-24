import uuid
from datetime import datetime, UTC
from typing import ClassVar

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC))

    workspaces = relationship("Workspace", back_populates="owner")
    workspace_memberships = relationship(
        "WorkspaceMember",
        foreign_keys="WorkspaceMember.user_id",
        back_populates="user",
    )

    workspace_id: ClassVar[uuid.UUID | None] = None