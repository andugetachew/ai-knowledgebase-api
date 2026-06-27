import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.postgres import get_db
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.models.sql.workspace_member import WorkspaceMember, MemberRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def get_workspace_access(
    workspace_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
    min_role: MemberRole = MemberRole.viewer,
) -> tuple:
    """Returns (workspace, user_role) or raises 403."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if workspace.owner_id == current_user.id:
        return workspace, MemberRole.owner

    member_result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    role_order = {MemberRole.viewer: 0, MemberRole.editor: 1, MemberRole.owner: 2}
    if role_order[member.role] < role_order[min_role]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return workspace, member.role