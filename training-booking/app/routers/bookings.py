from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import User, TrainingSession, Booking, WaitlistEntry, SessionGroupRestriction, UserGroupMembership, SiteSettings
from app.schemas import BookingCreate
from app.auth import get_current_active_user, require_admin_or_instructor
from app.services import audit, notifications

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("")
async def create_booking(data: BookingCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == data.session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.is_cancelled:
        raise HTTPException(status_code=400, detail="Session is cancelled")

    now = datetime.now(timezone.utc)
    session_dt = session.session_date
    if session_dt.tzinfo is None:
        session_dt = session_dt.replace(tzinfo=timezone.utc)
    if session_dt < now:
        raise HTTPException(status_code=400, detail="Cannot book a past session")

    # Check existing booking
    existing = db.execute(
        select(Booking).where(Booking.user_id == current_user.id).where(Booking.session_id == data.session_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Already booked")

    # Check group restrictions
    restrictions = db.execute(
        select(SessionGroupRestriction).where(SessionGroupRestriction.session_id == data.session_id)
    ).scalars().all()
    if restrictions:
        group_ids = {r.group_id for r in restrictions}
        user_groups = db.execute(
            select(UserGroupMembership.group_id).where(UserGroupMembership.user_id == current_user.id)
        ).scalars().all()
        if not group_ids.intersection(set(user_groups)):
            raise HTTPException(status_code=403, detail="Not in allowed group")

    # Check capacity
    count = db.execute(select(func.count(Booking.id)).where(Booking.session_id == data.session_id)).scalar() or 0
    if count >= session.max_participants:
        raise HTTPException(status_code=400, detail="Session is full")

    booking = Booking(user_id=current_user.id, session_id=data.session_id)
    db.add(booking)
    db.commit()
    db.refresh(booking)

    await notifications.booking_confirmed(current_user, session)
    await notifications.new_booking_admin(current_user, session)

    new_count = count + 1
    if new_count >= session.max_participants:
        await notifications.session_full_admin(session)

    await audit.log(db, current_user, "booking.created", "session", session.id, session.title, request=request)
    return {"id": booking.id, "session_id": booking.session_id, "booked_at": booking.booked_at.isoformat()}


@router.delete("/{session_id}")
async def cancel_booking(session_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    booking = db.execute(
        select(Booking).where(Booking.user_id == current_user.id).where(Booking.session_id == session_id)
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check cancel limit
    settings = db.execute(select(SiteSettings).where(SiteSettings.id == 1)).scalar_one_or_none()
    hours_limit = settings.cancel_hours_limit if settings else 2
    now = datetime.now(timezone.utc)
    session_dt = session.session_date
    if session_dt.tzinfo is None:
        session_dt = session_dt.replace(tzinfo=timezone.utc)
    if session_dt - now < timedelta(hours=hours_limit):
        raise HTTPException(status_code=400, detail=f"Cannot cancel less than {hours_limit} hours before session")

    db.delete(booking)
    db.flush()

    # Promote first waitlist entry
    next_stmt = (
        select(WaitlistEntry)
        .where(WaitlistEntry.session_id == session_id)
        .where(WaitlistEntry.status == "waiting")
        .order_by(WaitlistEntry.joined_at.asc())
    )
    next_entry = db.execute(next_stmt).scalar_one_or_none()
    if next_entry:
        hold = settings.waitlist_hold_minutes if settings else 30
        next_entry.status = "promoted"
        next_entry.promoted_at = now
        next_entry.expires_at = now + timedelta(minutes=hold)
        db.add(next_entry)
        await notifications.waitlist_promoted(next_entry.user, session, hold)

    db.commit()
    await notifications.booking_cancelled_by_user(current_user, session)
    await audit.log(db, current_user, "booking.cancelled", "session", session.id, session.title, request=request)
    return {"detail": "Booking cancelled"}


@router.get("/my")
async def my_bookings(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    now = datetime.now(timezone.utc)
    bookings = db.execute(
        select(Booking).join(TrainingSession).where(Booking.user_id == current_user.id).order_by(TrainingSession.session_date)
    ).scalars().all()
    result = []
    for b in bookings:
        s = b.session
        session_dt = s.session_date
        if session_dt.tzinfo is None:
            session_dt = session_dt.replace(tzinfo=timezone.utc)
        result.append({
            "id": b.id,
            "session_id": b.session_id,
            "booked_at": b.booked_at.isoformat(),
            "attended": b.attended,
            "is_upcoming": session_dt >= now,
            "session": {
                "id": s.id,
                "title": s.title,
                "session_date": s.session_date.isoformat(),
                "location": s.location,
                "online_link": s.online_link,
                "is_cancelled": s.is_cancelled,
                "activity_type": {"id": s.activity_type.id, "name": s.activity_type.name} if s.activity_type else None,
            },
        })
    return result


@router.get("/session/{session_id}")
async def session_bookings(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    bookings = db.execute(select(Booking).where(Booking.session_id == session_id)).scalars().all()
    return [
        {
            "id": b.id,
            "user_id": b.user_id,
            "first_name": b.user.first_name,
            "last_name": b.user.last_name,
            "phone": b.user.phone,
            "booked_at": b.booked_at.isoformat(),
            "attended": b.attended,
        }
        for b in bookings
    ]
