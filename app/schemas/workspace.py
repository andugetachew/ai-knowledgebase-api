import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.sql.workspace_member import MemberRole


class WorkspaceMemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role: MemberRole
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberWithEmail(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: MemberRole
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: MemberRole = MemberRole.viewer


class UpdateMemberRoleRequest(BaseModel):
    role: MemberRole


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)