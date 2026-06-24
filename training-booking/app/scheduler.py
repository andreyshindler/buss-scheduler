from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import TrainingSession, Booking, WaitlistEntry, Review
from app.services import notifications


def get_db() -> Session:
    return SessionLocal()


async def check_and_send_reminders():
    try:
        db = get_db()
        now = datetime.now(timezone.utc)
        lower = now + timedelta(hours=23)
        upper = now + timedelta(hours=25)
        stmt = (
            select(TrainingSession)
            .where(TrainingSession.is_cancelled == False)
            .where(TrainingSession.reminder_sent == False)
            .where(TrainingSession.session_date >= lower)
            .where(TrainingSession.session_date <= upper)
        )
        sessions = db.execute(stmt).scalars().all()
        for session in sessions:
            bookings = db.execute(select(Booking).where(Booking.session_id == session.id)).scalars().all()
            for booking in bookings:
                user = booking.user
                if user.telegram_chat_id:
                    await notifications.reminder_24h(user, session)
            session.reminder_sent = True
            db.add(session)
        db.commit()
        db.close()
    except Exception:
        pass


async def expire_waitlist_promotions():
    try:
        db = get_db()
        now = datetime.now(timezone.utc)
        stmt = (
            select(WaitlistEntry)
            .where(WaitlistEntry.status == "promoted")
            .where(WaitlistEntry.expires_at < now)
        )
        expired_entries = db.execute(stmt).scalars().all()
        for entry in expired_entries:
            entry.status = "expired"
            db.add(entry)
            db.flush()

            # Promote next waiting entry
            next_stmt = (
                select(WaitlistEntry)
                .where(WaitlistEntry.session_id == entry.session_id)
                .where(WaitlistEntry.status == "waiting")
                .order_by(WaitlistEntry.joined_at.asc())
            )
            next_entry = db.execute(next_stmt).scalar_one_or_none()
            if next_entry:
                session = db.execute(select(TrainingSession).where(TrainingSession.id == entry.session_id)).scalar_one_or_none()
                if session:
                    from app.models import SiteSettings as _SS
                    settings_row = db.execute(select(_SS).where(_SS.id == 1)).scalar_one_or_none()
                    hold_minutes = settings_row.waitlist_hold_minutes if settings_row else 30
                    next_entry.status = "promoted"
                    next_entry.promoted_at = now
                    next_entry.expires_at = now + timedelta(minutes=hold_minutes)
                    db.add(next_entry)
                    await notifications.waitlist_promoted(next_entry.user, session, hold_minutes)
        db.commit()
        db.close()
    except Exception:
        pass


async def review_reminder_job():
    try:
        db = get_db()
        now = datetime.now(timezone.utc)
        lower = now - timedelta(hours=25)
        upper = now - timedelta(hours=1)
        stmt = (
            select(TrainingSession)
            .where(TrainingSession.is_cancelled == False)
            .where(TrainingSession.review_reminder_sent == False)
            .where(TrainingSession.session_date >= lower)
            .where(TrainingSession.session_date <= upper)
        )
        sessions = db.execute(stmt).scalars().all()
        for session in sessions:
            bookings = db.execute(select(Booking).where(Booking.session_id == session.id)).scalars().all()
            for booking in bookings:
                user = booking.user
                if user.telegram_chat_id:
                    existing = db.execute(
                        select(Review).where(Review.user_id == user.id).where(Review.session_id == session.id)
                    ).scalar_one_or_none()
                    if not existing:
                        await notifications.review_reminder(user, session)
            session.review_reminder_sent = True
            db.add(session)
        db.commit()
        db.close()
    except Exception:
        pass


async def online_link_reminder_job():
    try:
        db = get_db()
        now = datetime.now(timezone.utc)
        lower = now + timedelta(minutes=25)
        upper = now + timedelta(minutes=35)
        stmt = (
            select(TrainingSession)
            .where(TrainingSession.online_link.isnot(None))
            .where(TrainingSession.online_link != "")
            .where(TrainingSession.is_cancelled == False)
            .where(TrainingSession.online_link_reminder_sent == False)
            .where(TrainingSession.session_date >= lower)
            .where(TrainingSession.session_date <= upper)
        )
        sessions = db.execute(stmt).scalars().all()
        for session in sessions:
            bookings = db.execute(select(Booking).where(Booking.session_id == session.id)).scalars().all()
            for booking in bookings:
                user = booking.user
                if user.telegram_chat_id:
                    await notifications.online_link_reminder(user, session)
            session.online_link_reminder_sent = True
            db.add(session)
        db.commit()
        db.close()
    except Exception:
        pass


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send_reminders, "interval", hours=1)
    scheduler.add_job(expire_waitlist_promotions, "interval", minutes=5)
    scheduler.add_job(review_reminder_job, "interval", hours=1)
    scheduler.add_job(online_link_reminder_job, "interval", minutes=5)
    return scheduler
