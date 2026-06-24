from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.database import get_db
from app.models import User, Booking, TrainingSession, ActivityType, Review
from app.schemas import UserOut, UserUpdate, TwoFACodeRequest
from app.auth import get_current_active_user, hash_password
from app.services import audit, two_factor, notifications

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.put("/me", response_model=UserOut)
async def update_me(data: UserUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if data.first_name is not None:
        current_user.first_name = data.first_name
    if data.last_name is not None:
        current_user.last_name = data.last_name
    if data.phone is not None and data.phone != current_user.phone:
        existing = db.execute(select(User).where(User.phone == data.phone)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Phone already in use")
        current_user.phone = data.phone
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    await audit.log(db, current_user, "user.profile_updated", "user", current_user.id, current_user.phone, request=request)
    return current_user


@router.get("/me/history")
async def get_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    stmt = (
        select(Booking, TrainingSession)
        .join(TrainingSession, Booking.session_id == TrainingSession.id)
        .where(Booking.user_id == current_user.id)
        .where(TrainingSession.session_date < now)
        .order_by(TrainingSession.session_date.desc())
    )
    rows = db.execute(stmt).all()
    result = []
    for booking, session in rows:
        review = db.execute(
            select(Review).where(Review.user_id == current_user.id).where(Review.session_id == session.id)
        ).scalar_one_or_none()
        result.append({
            "booking_id": booking.id,
            "session_id": session.id,
            "title": session.title,
            "session_date": session.session_date.isoformat(),
            "location": session.location,
            "attended": booking.attended,
            "review_submitted": review is not None,
            "activity_type": {"id": session.activity_type.id, "name": session.activity_type.name} if session.activity_type else None,
        })
    return result


@router.get("/me/stats")
async def get_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    total = db.execute(
        select(func.count(Booking.id))
        .join(TrainingSession)
        .where(Booking.user_id == current_user.id)
        .where(TrainingSession.session_date < now)
    ).scalar() or 0

    # Find most frequent activity type
    rows = db.execute(
        select(ActivityType.name, func.count(Booking.id).label("cnt"))
        .join(TrainingSession, Booking.session_id == TrainingSession.id)
        .join(ActivityType, TrainingSession.activity_type_id == ActivityType.id)
        .where(Booking.user_id == current_user.id)
        .where(TrainingSession.session_date < now)
        .group_by(ActivityType.id)
        .order_by(func.count(Booking.id).desc())
    ).first()

    return {"total_sessions": total, "favorite_activity": rows[0] if rows else None}


@router.post("/me/2fa/enable")
async def enable_2fa(data: TwoFACodeRequest, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Connect Telegram first to use 2FA")
    if current_user.twofa_enabled:
        raise HTTPException(status_code=400, detail="2FA already enabled")

    ok = two_factor.verify_2fa_code(db, current_user.id, data.code, "2fa_enable")
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    current_user.twofa_enabled = True
    db.commit()
    await notifications.twofa_enabled_msg(current_user)
    await audit.log(db, current_user, "user.2fa_enabled", "user", current_user.id, current_user.phone, request=request)
    return {"detail": "2FA enabled"}


@router.post("/me/2fa/disable")
async def disable_2fa(data: TwoFACodeRequest, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if not current_user.twofa_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled")

    ok = two_factor.verify_2fa_code(db, current_user.id, data.code, "2fa_disable")
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    current_user.twofa_enabled = False
    db.commit()
    await notifications.twofa_disabled_msg(current_user)
    await audit.log(db, current_user, "user.2fa_disabled", "user", current_user.id, current_user.phone, request=request)
    return {"detail": "2FA disabled"}


@router.post("/me/2fa/send-code")
async def send_2fa_code(purpose: str = "2fa_enable", db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Connect Telegram first")
    code = two_factor.create_2fa_code(db, current_user.id, purpose)
    await notifications.twofa_code(current_user, code)
    return {"detail": "Code sent"}
