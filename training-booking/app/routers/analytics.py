from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import User, TrainingSession, Booking
from app.auth import require_admin_or_instructor, require_admin

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/fill-trend")
async def fill_trend(weeks: int = Query(12, ge=1, le=52), db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    now = datetime.now(timezone.utc)
    result = []
    for i in range(weeks - 1, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        sessions = db.execute(
            select(TrainingSession)
            .where(TrainingSession.session_date >= week_start)
            .where(TrainingSession.session_date < week_end)
            .where(TrainingSession.is_cancelled == False)
        ).scalars().all()
        if sessions:
            total_pct = 0
            for s in sessions:
                count = db.execute(select(func.count(Booking.id)).where(Booking.session_id == s.id)).scalar() or 0
                pct = (count / s.max_participants * 100) if s.max_participants > 0 else 0
                total_pct += pct
            avg_pct = total_pct / len(sessions)
        else:
            avg_pct = 0
        label = week_start.strftime("%d/%m")
        result.append({"week": label, "fill_pct": round(avg_pct, 1), "session_count": len(sessions)})
    return result


@router.get("/top-users")
async def top_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    rows = db.execute(
        select(User.id, User.first_name, User.last_name, func.count(Booking.id).label("cnt"))
        .join(Booking, Booking.user_id == User.id)
        .group_by(User.id)
        .order_by(func.count(Booking.id).desc())
        .limit(10)
    ).all()
    return [{"user_id": r[0], "name": f"{r[1]} {r[2]}", "count": r[3]} for r in rows]


@router.get("/cancel-timing")
async def cancel_timing(db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    from app.models import AuditLog
    import json
    rows = db.execute(
        select(AuditLog).where(AuditLog.action == "booking.cancelled")
    ).scalars().all()

    buckets = {"<1h": 0, "1-6h": 0, "6-24h": 0, "24-72h": 0, ">72h": 0}
    hours_list = []
    for row in rows:
        try:
            details = json.loads(row.details) if row.details else {}
            hours_before = details.get("hours_before")
            if hours_before is not None:
                h = float(hours_before)
                hours_list.append(h)
                if h < 1:
                    buckets["<1h"] += 1
                elif h < 6:
                    buckets["1-6h"] += 1
                elif h < 24:
                    buckets["6-24h"] += 1
                elif h < 72:
                    buckets["24-72h"] += 1
                else:
                    buckets[">72h"] += 1
        except Exception:
            pass

    avg_hours = sum(hours_list) / len(hours_list) if hours_list else 0
    total = sum(buckets.values())
    result = []
    for label, count in buckets.items():
        pct = round(count / total * 100, 1) if total > 0 else 0
        result.append({"label": label, "count": count, "pct": pct})
    return {"buckets": result, "avg_hours": round(avg_hours, 1), "total": total}
