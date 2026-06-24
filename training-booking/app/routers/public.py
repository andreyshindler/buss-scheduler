import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import TrainingSession, Booking, SiteSettings

router = APIRouter(prefix="/api/public", tags=["public"])
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")


def _fmt_he(dt: datetime) -> str:
    days_he = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
    months_he = ["", "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
    return f"יום {days_he[dt.weekday()]}, {dt.day} ב{months_he[dt.month]} {dt.year} {dt.strftime('%H:%M')}"


def _fmt_en(dt: datetime) -> str:
    return dt.strftime("%A, %B %d %Y %H:%M")


@router.get("/upcoming-sessions")
async def upcoming_sessions(
    limit: int = Query(5, ge=1, le=20),
    activity_type_id: Optional[int] = None,
    lang: str = Query("he"),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    stmt = (
        select(TrainingSession)
        .where(TrainingSession.session_date >= now)
        .where(TrainingSession.is_cancelled == False)
        .order_by(TrainingSession.session_date.asc())
        .limit(limit)
    )
    if activity_type_id:
        stmt = stmt.where(TrainingSession.activity_type_id == activity_type_id)

    sessions = db.execute(stmt).scalars().all()
    total = db.execute(
        select(func.count(TrainingSession.id))
        .where(TrainingSession.session_date >= now)
        .where(TrainingSession.is_cancelled == False)
    ).scalar() or 0

    result = []
    for s in sessions:
        count = db.execute(select(func.count(Booking.id)).where(Booking.session_id == s.id)).scalar() or 0
        spots_left = max(0, s.max_participants - count)
        fmt_date = _fmt_he(s.session_date) if lang == "he" else _fmt_en(s.session_date)
        cover_url = f"{SERVER_BASE_URL}/uploads/sessions/{s.cover_image_filename}" if s.cover_image_filename else None
        result.append({
            "id": s.id,
            "title": s.title,
            "session_date": s.session_date.isoformat(),
            "session_date_formatted": fmt_date,
            "activity_type": {"id": s.activity_type.id, "name": s.activity_type.name} if s.activity_type else None,
            "location": s.location,
            "spots_total": s.max_participants,
            "spots_taken": count,
            "spots_left": spots_left,
            "is_full": spots_left == 0,
            "cover_image_url": cover_url,
            "booking_url": f"{SERVER_BASE_URL}/#book/{s.id}",
            "is_online": bool(s.online_link),
        })

    return {
        "sessions": result,
        "total": total,
        "generated_at": now.isoformat(),
        "booking_app_url": SERVER_BASE_URL,
    }


@router.get("/widget-config")
async def widget_config(db: Session = Depends(get_db)):
    settings = db.execute(select(SiteSettings).where(SiteSettings.id == 1)).scalar_one_or_none()
    logo_url = None
    app_name = "Training Booking"
    primary_color = "#2563eb"
    if settings:
        app_name = settings.app_name
        primary_color = settings.primary_color
        if settings.logo_filename:
            logo_url = f"{SERVER_BASE_URL}/uploads/logo/{settings.logo_filename}"
    return {
        "logo_url": logo_url,
        "app_name": app_name,
        "primary_color": primary_color,
        "booking_app_url": SERVER_BASE_URL,
    }
