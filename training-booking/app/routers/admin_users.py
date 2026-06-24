from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.schemas import BlockUserRequest, AdminUserOut
from app.auth import require_admin, get_current_active_user
from app.services import audit, notifications

router = APIRouter(prefix="/api/admin", tags=["admin-users"])


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    return users


@router.post("/users/{user_id}/block")
async def block_user(user_id: int, data: BlockUserRequest, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    user.is_blocked = True
    user.block_reason = data.reason
    user.blocked_at = datetime.now(timezone.utc)
    user.blocked_by_id = current_user.id
    db.commit()
    await notifications.account_blocked(user, data.reason)
    await audit.log(db, current_user, "user.blocked", "user", user.id, f"{user.first_name} {user.last_name}", details={"reason": data.reason}, request=request)
    return {"detail": "User blocked"}


@router.post("/users/{user_id}/unblock")
async def unblock_user(user_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    user.is_blocked = False
    user.block_reason = None
    user.blocked_at = None
    user.blocked_by_id = None
    db.commit()
    await notifications.account_unblocked(user)
    await audit.log(db, current_user, "user.unblocked", "user", user.id, f"{user.first_name} {user.last_name}", request=request)
    return {"detail": "User unblocked"}


@router.put("/users/{user_id}/role")
async def update_role(user_id: int, body: dict, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    role = body.get("role")
    if role not in ("user", "instructor", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    user.role = role
    db.commit()
    await audit.log(db, current_user, "user.role_updated", "user", user.id, f"{user.first_name} {user.last_name}", details={"role": role}, request=request)
    return {"detail": "Role updated"}


@router.get("/dashboard")
async def dashboard(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    from datetime import timedelta
    from sqlalchemy import func
    from app.models import TrainingSession, Booking, Review, SiteSettings

    now = datetime.now(timezone.utc)
    week_end = now + timedelta(days=7)

    total_users = db.execute(select(func.count(User.id))).scalar() or 0
    upcoming_sessions = db.execute(
        select(TrainingSession).where(TrainingSession.session_date >= now).where(TrainingSession.is_cancelled == False).order_by(TrainingSession.session_date).limit(10)
    ).scalars().all()

    sessions_data = []
    for s in upcoming_sessions:
        count = db.execute(select(func.count(Booking.id)).where(Booking.session_id == s.id)).scalar() or 0
        pct = round(count / s.max_participants * 100, 1) if s.max_participants > 0 else 0
        sessions_data.append({
            "id": s.id,
            "title": s.title,
            "session_date": s.session_date.isoformat(),
            "booking_count": count,
            "max_participants": s.max_participants,
            "fill_pct": pct,
        })

    # Avg fill rate for all sessions in past 30 days
    past_sessions = db.execute(
        select(TrainingSession)
        .where(TrainingSession.session_date >= now - timedelta(days=30))
        .where(TrainingSession.session_date < now)
        .where(TrainingSession.is_cancelled == False)
    ).scalars().all()

    avg_fill = 0
    if past_sessions:
        total_pct = 0
        for s in past_sessions:
            count = db.execute(select(func.count(Booking.id)).where(Booking.session_id == s.id)).scalar() or 0
            total_pct += (count / s.max_participants * 100) if s.max_participants > 0 else 0
        avg_fill = round(total_pct / len(past_sessions), 1)

    return {
        "total_users": total_users,
        "upcoming_sessions": sessions_data,
        "avg_fill_rate": avg_fill,
    }
