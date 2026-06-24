from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models import User, UserGroup, UserGroupMembership
from app.schemas import UserGroupCreate, UserGroupUpdate, UserGroupOut
from app.auth import require_admin, get_current_active_user
from app.services import audit

router = APIRouter(prefix="/api/user-groups", tags=["user-groups"])


@router.get("", response_model=list[UserGroupOut])
async def list_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = db.execute(select(UserGroup).order_by(UserGroup.name)).scalars().all()
    return rows


@router.post("", response_model=UserGroupOut)
async def create_group(data: UserGroupCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    existing = db.execute(select(UserGroup).where(UserGroup.name == data.name)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Group name already exists")
    group = UserGroup(name=data.name, description=data.description, created_by_id=current_user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.put("/{group_id}", response_model=UserGroupOut)
async def update_group(group_id: int, data: UserGroupUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    group = db.execute(select(UserGroup).where(UserGroup.id == group_id)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Not found")
    group.name = data.name
    group.description = data.description
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{group_id}")
async def delete_group(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    group = db.execute(select(UserGroup).where(UserGroup.id == group_id)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(group)
    db.commit()
    return {"detail": "Deleted"}


@router.get("/{group_id}/members")
async def list_members(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    group = db.execute(select(UserGroup).where(UserGroup.id == group_id)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Not found")
    members = db.execute(
        select(UserGroupMembership, User)
        .join(User, UserGroupMembership.user_id == User.id)
        .where(UserGroupMembership.group_id == group_id)
    ).all()
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "phone": u.phone,
            "added_at": m.added_at.isoformat(),
        }
        for m, u in members
    ]


@router.post("/{group_id}/members")
async def add_member(group_id: int, body: dict, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    group = db.execute(select(UserGroup).where(UserGroup.id == group_id)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.execute(
        select(UserGroupMembership)
        .where(UserGroupMembership.user_id == user_id)
        .where(UserGroupMembership.group_id == group_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    m = UserGroupMembership(user_id=user_id, group_id=group_id, added_by_id=current_user.id)
    db.add(m)
    db.commit()
    return {"detail": "Added"}


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    m = db.execute(
        select(UserGroupMembership)
        .where(UserGroupMembership.user_id == user_id)
        .where(UserGroupMembership.group_id == group_id)
    ).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(m)
    db.commit()
    return {"detail": "Removed"}
