import uuid
from datetime import datetime, UTC
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC))

    owner = relationship("User", back_populates="workspaces")
    documents = relationship("Document", back_populates="workspace")
    members = relationship("WorkspaceMember", back_populates="workspace")
    subscription = relationship("Subscription", back_populates="workspace", uselist=False)