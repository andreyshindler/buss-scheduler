import os
import io
import uuid
import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete

from app.database import get_db
from app.models import (
    User, TrainingSession, Booking, WaitlistEntry, Review, ActivityType,
    BlockedDate, SessionGroupRestriction, UserGroup, SiteSettings
)
from app.schemas import SessionCreate, SessionUpdate, SessionOut, AttendanceUpdate
from app.auth import get_current_active_user, require_admin_or_instructor, get_current_user
from app.services import audit, notifications, pdf_generator

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")
UPLOAD_DIR = "uploads/sessions"


def _google_calendar_url(session: TrainingSession) -> str:
    start = session.session_date.strftime("%Y%m%dT%H%M%SZ")
    end = (session.session_date + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
    title = quote(session.title)
    desc = quote(session.description or "")
    loc = quote(session.location or "")
    return f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={start}/{end}&details={desc}&location={loc}"


def _session_to_out(session: TrainingSession, db: Session) -> dict:
    count = db.execute(select(func.count(Booking.id)).where(Booking.session_id == session.id)).scalar() or 0
    avg = db.execute(select(func.avg(Review.stars)).where(Review.session_id == session.id)).scalar()
    is_restricted = len(session.group_restrictions) > 0
    cover_url = None
    if session.cover_image_filename:
        cover_url = f"{SERVER_BASE_URL}/uploads/sessions/{session.cover_image_filename}"
    return {
        "id": session.id,
        "title": session.title,
        "description": session.description,
        "activity_type_id": session.activity_type_id,
        "activity_type": {"id": session.activity_type.id, "name": session.activity_type.name} if session.activity_type else None,
        "instructor_id": session.instructor_id,
        "instructor": {"id": session.instructor.id, "first_name": session.instructor.first_name, "last_name": session.instructor.last_name} if session.instructor else None,
        "session_date": session.session_date.isoformat(),
        "max_participants": session.max_participants,
        "location": session.location,
        "location_lat": session.location_lat,
        "location_lng": session.location_lng,
        "requirements": session.requirements,
        "cover_image_filename": session.cover_image_filename,
        "cover_image_url": cover_url,
        "online_link": session.online_link,
        "is_cancelled": session.is_cancelled,
        "recurring_group_id": session.recurring_group_id,
        "created_at": session.created_at.isoformat(),
        "booking_count": count,
        "avg_rating": round(float(avg), 1) if avg else None,
        "google_calendar_url": _google_calendar_url(session),
        "is_restricted": is_restricted,
    }


def _can_manage_session(current_user: User, session: TrainingSession) -> bool:
    return current_user.role == "admin" or session.instructor_id == current_user.id or session.created_by_id == current_user.id


@router.get("")
async def list_sessions(
    search: Optional[str] = None,
    activity_type_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    availability: Optional[str] = None,
    status_filter: Optional[str] = None,
    my_only: bool = False,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    stmt = select(TrainingSession).order_by(TrainingSession.session_date.asc())
    if search:
        stmt = stmt.where(TrainingSession.title.ilike(f"%{search}%"))
    if activity_type_id:
        stmt = stmt.where(TrainingSession.activity_type_id == activity_type_id)
    if date_from:
        stmt = stmt.where(TrainingSession.session_date >= datetime.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(TrainingSession.session_date <= datetime.fromisoformat(date_to))
    if location:
        stmt = stmt.where(TrainingSession.location.ilike(f"%{location}%"))
    if status_filter == "upcoming":
        stmt = stmt.where(TrainingSession.session_date >= datetime.now(timezone.utc)).where(TrainingSession.is_cancelled == False)
    elif status_filter == "past":
        stmt = stmt.where(TrainingSession.session_date < datetime.now(timezone.utc))
    elif status_filter == "cancelled":
        stmt = stmt.where(TrainingSession.is_cancelled == True)
    if my_only and current_user:
        stmt = stmt.where(
            (TrainingSession.instructor_id == current_user.id) | (TrainingSession.created_by_id == current_user.id)
        )
    sessions = db.execute(stmt).scalars().all()
    result = []
    for s in sessions:
        out = _session_to_out(s, db)
        if availability == "available":
            if out["booking_count"] >= s.max_participants:
                continue
        elif availability == "full":
            if out["booking_count"] < s.max_participants:
                continue
        result.append(out)
    return result


@router.get("/{session_id}")
async def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    return _session_to_out(session, db)


@router.post("")
async def create_session(data: SessionCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    blocked_dates_rows = db.execute(select(BlockedDate)).scalars().all()
    blocked_set = {bd.date for bd in blocked_dates_rows}

    sessions_to_create = []
    base_date = data.session_date

    if data.recurring_freq and data.recurring_until:
        delta = timedelta(weeks=1) if data.recurring_freq == "weekly" else timedelta(weeks=2)
        current_date = base_date
        group_id = str(uuid.uuid4())
        count = 0
        skipped = 0
        while current_date <= data.recurring_until and count < 52:
            date_str = current_date.date().isoformat()
            if date_str in blocked_set:
                skipped += 1
            else:
                sessions_to_create.append((current_date, group_id))
                count += 1
            current_date += delta
    else:
        sessions_to_create = [(base_date, None)]
        skipped = 0

    created = []
    for s_date, group_id in sessions_to_create:
        s = TrainingSession(
            title=data.title,
            description=data.description,
            activity_type_id=data.activity_type_id,
            instructor_id=data.instructor_id if current_user.role == "admin" else current_user.id,
            session_date=s_date,
            max_participants=data.max_participants,
            location=data.location,
            location_lat=data.location_lat,
            location_lng=data.location_lng,
            requirements=data.requirements,
            online_link=data.online_link,
            recurring_group_id=group_id,
            created_by_id=current_user.id,
        )
        db.add(s)
        db.flush()
        for gid in data.allowed_group_ids:
            db.add(SessionGroupRestriction(session_id=s.id, group_id=gid))
        created.append(s)

    db.commit()
    for s in created:
        await audit.log(db, current_user, "session.created", "session", s.id, s.title, request=request)

    if len(created) == 1:
        db.refresh(created[0])
        return _session_to_out(created[0], db)
    return {"created_count": len(created), "skipped_count": skipped}


@router.put("/{session_id}")
async def update_session(session_id: int, data: SessionUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")

    for k, v in data.model_dump(exclude={"allowed_group_ids"}).items():
        if v is not None:
            setattr(session, k, v)

    if data.allowed_group_ids is not None:
        db.execute(
            delete(SessionGroupRestriction)
            .where(SessionGroupRestriction.session_id == session_id)
        )
        for gid in data.allowed_group_ids:
            db.add(SessionGroupRestriction(session_id=session_id, group_id=gid))

    db.commit()
    db.refresh(session)
    await audit.log(db, current_user, "session.updated", "session", session.id, session.title, request=request)
    return _session_to_out(session, db)


@router.delete("/{session_id}")
async def delete_session(session_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")
    bookings = db.execute(select(Booking).where(Booking.session_id == session_id)).first()
    if bookings:
        raise HTTPException(status_code=400, detail="Cannot delete session with bookings")
    db.delete(session)
    db.commit()
    await audit.log(db, current_user, "session.deleted", "session", session_id, session.title, request=request)
    return {"detail": "Deleted"}


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")
    session.is_cancelled = True
    db.commit()
    # Notify all booked users
    bookings = db.execute(select(Booking).where(Booking.session_id == session_id)).scalars().all()
    for booking in bookings:
        await notifications.session_cancelled_notify(booking.user, session)
    await audit.log(db, current_user, "session.cancelled", "session", session.id, session.title, request=request)
    return {"detail": "Session cancelled"}


@router.post("/{session_id}/cover")
async def upload_cover(session_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")

    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Invalid file type")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if session.cover_image_filename:
        old = os.path.join(UPLOAD_DIR, session.cover_image_filename)
        if os.path.exists(old):
            os.remove(old)

    session.cover_image_filename = filename
    db.commit()
    await audit.log(db, current_user, "session.cover_uploaded", "session", session.id, session.title)
    return {"filename": filename}


@router.delete("/{session_id}/cover")
async def delete_cover(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if session.cover_image_filename:
        filepath = os.path.join(UPLOAD_DIR, session.cover_image_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    session.cover_image_filename = None
    db.commit()
    return {"detail": "Removed"}


@router.get("/{session_id}/ics")
async def download_ics(session_id: int, db: Session = Depends(get_db)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")

    def _esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace(",", "\\,").replace("\n", "\\n")

    dt = session.session_date
    # Assume stored as UTC or naive (treat as UTC+3 / Israel)
    from zoneinfo import ZoneInfo
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("Asia/Jerusalem"))
    dt_utc = dt.astimezone(timezone.utc)
    end_utc = dt_utc + timedelta(hours=1)

    fmt = "%Y%m%dT%H%M%SZ"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TrainingBooking//HE",
        "BEGIN:VEVENT",
        f"DTSTART:{dt_utc.strftime(fmt)}",
        f"DTEND:{end_utc.strftime(fmt)}",
        f"SUMMARY:{_esc(session.title)}",
    ]
    if session.description:
        lines.append(f"DESCRIPTION:{_esc(session.description)}")
    if session.location:
        lines.append(f"LOCATION:{_esc(session.location)}")
    if session.online_link:
        lines.append(f"URL:{session.online_link}")
    if session.is_cancelled:
        lines.append("STATUS:CANCELLED")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    content = "\r\n".join(lines) + "\r\n"
    return Response(
        content=content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.ics"'},
    )


@router.get("/{session_id}/attendance")
async def get_attendance(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")
    bookings = db.execute(select(Booking).where(Booking.session_id == session_id)).scalars().all()
    return [
        {
            "booking_id": b.id,
            "user_id": b.user_id,
            "first_name": b.user.first_name,
            "last_name": b.user.last_name,
            "phone": b.user.phone,
            "attended": b.attended,
        }
        for b in bookings
    ]


@router.post("/{session_id}/attendance/{user_id}")
async def mark_attendance(session_id: int, user_id: int, data: AttendanceUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")
    now = datetime.now(timezone.utc)
    if session.session_date.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(status_code=400, detail="Can only mark attendance for past sessions")
    booking = db.execute(
        select(Booking).where(Booking.session_id == session_id).where(Booking.user_id == user_id)
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.attended = data.attended
    db.commit()
    await audit.log(db, current_user, "session.attendance_marked", "booking", booking.id, f"session:{session_id} user:{user_id}", request=request)
    return {"detail": "Updated"}


@router.get("/{session_id}/export/csv")
async def export_csv(session_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")
    bookings = db.execute(select(Booking).where(Booking.session_id == session_id)).scalars().all()
    lines = ["שם פרטי,שם משפחה,טלפון,תאריך הרשמה,נוכחות"]
    for b in bookings:
        attended = "כן" if b.attended else ("לא" if b.attended is False else "")
        lines.append(f"{b.user.first_name},{b.user.last_name},{b.user.phone},{b.booked_at.strftime('%d/%m/%Y %H:%M')},{attended}")
    content = "\n".join(lines)
    await audit.log(db, current_user, "admin.export_csv", "session", session_id, session.title, request=request)
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.csv"'},
    )


@router.get("/{session_id}/export/excel")
async def export_excel(session_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    import openpyxl, io
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")
    bookings = db.execute(select(Booking).where(Booking.session_id == session_id)).scalars().all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Participants"
    ws.append(["שם פרטי", "שם משפחה", "טלפון", "תאריך הרשמה", "נוכחות"])
    for b in bookings:
        attended = "כן" if b.attended else ("לא" if b.attended is False else "")
        ws.append([b.user.first_name, b.user.last_name, b.user.phone, b.booked_at.strftime("%d/%m/%Y %H:%M"), attended])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    await audit.log(db, current_user, "admin.export_excel", "session", session_id, session.title, request=request)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.xlsx"'},
    )


@router.get("/{session_id}/pdf/attendance")
async def pdf_attendance(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    if not _can_manage_session(current_user, session):
        raise HTTPException(status_code=403, detail="Forbidden")
    bookings = db.execute(select(Booking).where(Booking.session_id == session_id)).scalars().all()
    settings = db.execute(select(SiteSettings).where(SiteSettings.id == 1)).scalar_one_or_none()
    logo_path = None
    if settings and settings.logo_filename:
        logo_path = os.path.join("uploads/logo", settings.logo_filename)
    pdf_bytes = pdf_generator.generate_attendance_pdf(session, bookings, logo_path)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="attendance-{session_id}.pdf"'},
    )


@router.get("/{session_id}/pdf/card")
async def pdf_card(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    settings = db.execute(select(SiteSettings).where(SiteSettings.id == 1)).scalar_one_or_none()
    logo_path = None
    if settings and settings.logo_filename:
        logo_path = os.path.join("uploads/logo", settings.logo_filename)
    pdf_bytes = pdf_generator.generate_session_card_pdf(session, logo_path)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="card-{session_id}.pdf"'},
    )
