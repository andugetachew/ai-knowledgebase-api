import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.postgres import get_db
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.models.sql.workspace_member import WorkspaceMember, MemberRole
from app.schemas.workspace import (
    InviteMemberRequest,
    UpdateMemberRoleRequest,
    WorkspaceMemberWithEmail,
    WorkspaceOut,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


async def get_workspace_or_403(
    workspace_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
    require_owner: bool = False,
) -> Workspace:
    print("!!! get_workspace_or_403 CALLED !!!")
    print("!!! get_workspace_or_403 CALLED !!!")
    print("MODULE FILE:", __file__)
    """Get workspace and verify user has access. Raises 404 or 403."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    is_owner = workspace.owner_id == current_user.id

    if require_owner and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the workspace owner can do this")

    if not is_owner:
        member_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace")

    return workspace


@router.get("/", response_model=list[WorkspaceOut])
async def list_my_workspaces(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all workspaces the user owns or is a member of."""
    owned = await db.execute(
        select(Workspace).where(Workspace.owner_id == current_user.id)
    )
    owned_workspaces = owned.scalars().all()

    member_result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
    )
    member_workspaces = member_result.scalars().all()

    seen = {w.id for w in owned_workspaces}
    all_workspaces = list(owned_workspaces)
    for w in member_workspaces:
        if w.id not in seen:
            all_workspaces.append(w)

    return all_workspaces


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberWithEmail])
async def list_members(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_workspace_or_403(workspace_id, current_user, db)

    result = await db.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .options(selectinload(WorkspaceMember.user))
    )
    members = result.scalars().all()

    return [
        WorkspaceMemberWithEmail(
            id=m.id,
            user_id=m.user_id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role,
            created_at=m.created_at,
        )
        for m in members
    ]


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def invite_member(
    workspace_id: uuid.UUID,
    payload: InviteMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only owner or editor can invite members."""
    workspace = await get_workspace_or_403(workspace_id, current_user, db)

    is_owner = workspace.owner_id == current_user.id
    if not is_owner:
        role_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        member = role_result.scalar_one_or_none()
        if not member or member.role == MemberRole.viewer:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot invite members")

    # find user by email
    user_result = await db.execute(
        select(User).where(User.email == payload.email)
    )
    invited_user = user_result.scalar_one_or_none()
    if not invited_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if invited_user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot invite yourself")

    # check already a member
    existing = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == invited_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a member")

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=invited_user.id,
        role=payload.role,
        invited_by=current_user.id,
    )
    db.add(member)
    await db.commit()

    return {"message": f"{invited_user.email} added as {payload.role}"}


@router.patch("/{workspace_id}/members/{user_id}")
async def update_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only owner can change roles."""
    await get_workspace_or_403(workspace_id, current_user, db, require_owner=True)

    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    member.role = payload.role
    await db.commit()

    return {"message": f"Role updated to {payload.role}"}


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Owner can remove anyone. Members can remove themselves."""
    workspace = await get_workspace_or_403(workspace_id, current_user, db)

    is_owner = workspace.owner_id == current_user.id
    is_self = user_id == current_user.id

    if not is_owner and not is_self:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    await db.delete(member)
    await db.commit()

