from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import User, TrainingSession, WaitlistEntry, Booking, SiteSettings
from app.auth import get_current_active_user, require_admin_or_instructor
from app.services import audit, notifications

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


@router.post("/{session_id}")
async def join_waitlist(session_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if session.is_cancelled:
        raise HTTPException(status_code=400, detail="Session is cancelled")

    now = datetime.now(timezone.utc)
    session_dt = session.session_date.replace(tzinfo=timezone.utc) if not session.session_date.tzinfo else session.session_date
    if session_dt < now:
        raise HTTPException(status_code=400, detail="Session is past")

    existing_booking = db.execute(
        select(Booking).where(Booking.user_id == current_user.id).where(Booking.session_id == session_id)
    ).scalar_one_or_none()
    if existing_booking:
        raise HTTPException(status_code=400, detail="Already booked")

    existing_waitlist = db.execute(
        select(WaitlistEntry)
        .where(WaitlistEntry.user_id == current_user.id)
        .where(WaitlistEntry.session_id == session_id)
        .where(WaitlistEntry.status.in_(["waiting", "promoted"]))
    ).scalar_one_or_none()
    if existing_waitlist:
        raise HTTPException(status_code=400, detail="Already on waitlist")

    # Only join if full
    count = db.execute(select(func.count(Booking.id)).where(Booking.session_id == session_id)).scalar() or 0
    if count < session.max_participants:
        raise HTTPException(status_code=400, detail="Session not full, book directly")

    entry = WaitlistEntry(user_id=current_user.id, session_id=session_id, status="waiting")
    db.add(entry)
    db.commit()

    position = db.execute(
        select(func.count(WaitlistEntry.id))
        .where(WaitlistEntry.session_id == session_id)
        .where(WaitlistEntry.status == "waiting")
        .where(WaitlistEntry.joined_at <= entry.joined_at)
    ).scalar() or 1

    await audit.log(db, current_user, "booking.waitlist_joined", "session", session.id, session.title, request=request)
    return {"detail": "Added to waitlist", "position": position}


@router.delete("/{session_id}")
async def leave_waitlist(session_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    entry = db.execute(
        select(WaitlistEntry)
        .where(WaitlistEntry.user_id == current_user.id)
        .where(WaitlistEntry.session_id == session_id)
        .where(WaitlistEntry.status.in_(["waiting", "promoted"]))
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Not on waitlist")
    entry.status = "expired"
    db.commit()
    await audit.log(db, current_user, "booking.waitlist_left", "session", session_id, None, request=request)
    return {"detail": "Removed from waitlist"}


@router.get("/{session_id}")
async def get_waitlist(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    entries = db.execute(
        select(WaitlistEntry)
        .where(WaitlistEntry.session_id == session_id)
        .where(WaitlistEntry.status.in_(["waiting", "promoted"]))
        .order_by(WaitlistEntry.joined_at)
    ).scalars().all()
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "first_name": e.user.first_name,
            "last_name": e.user.last_name,
            "phone": e.user.phone,
            "joined_at": e.joined_at.isoformat(),
            "status": e.status,
            "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        }
        for e in entries
    ]
