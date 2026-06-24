import os
from datetime import datetime
from app.services.telegram import send_to_admin, send_to_user
from app.models import User, TrainingSession

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")


async def booking_confirmed(user: User, session: TrainingSession) -> None:
    msg = (
        f"✅ ההרשמה שלך ל'{session.title}' ב-{_fmt_date(session.session_date)} אושרה!\n"
        f"📍 {session.location or ''}\n"
        f"📅 {SERVER_BASE_URL}/api/sessions/{session.id}/ics"
    )
    if user.telegram_chat_id:
        await send_to_user(user.telegram_chat_id, msg)


async def new_booking_admin(user: User, session: TrainingSession) -> None:
    msg = f"✅ {user.first_name} {user.last_name} ({user.phone}) נרשם ל'{session.title}' ב-{_fmt_date(session.session_date)}"
    await send_to_admin(msg)


async def session_full_admin(session: TrainingSession) -> None:
    msg = f"🔴 '{session.title}' ב-{_fmt_date(session.session_date)} מלא! ({session.max_participants}/{session.max_participants})"
    await send_to_admin(msg)


async def booking_cancelled_by_user(user: User, session: TrainingSession) -> None:
    msg = f"🔔 {user.first_name} {user.last_name} ({user.phone}) ביטל הרשמה ל'{session.title}' ב-{_fmt_date(session.session_date)}"
    await send_to_admin(msg)


async def reminder_24h(user: User, session: TrainingSession) -> None:
    if not user.telegram_chat_id:
        return
    msg = (
        f"⏰ תזכורת: יש לך אימון מחר!\n"
        f"📌 {session.title}\n"
        f"🕐 {_fmt_date(session.session_date)}\n"
        f"📍 {session.location or ''}"
    )
    await send_to_user(user.telegram_chat_id, msg)


async def online_link_reminder(user: User, session: TrainingSession) -> None:
    if not user.telegram_chat_id or not session.online_link:
        return
    msg = (
        f"🎥 האימון '{session.title}' מתחיל בעוד 30 דקות!\n"
        f"🔗 הצטרף: {session.online_link}"
    )
    await send_to_user(user.telegram_chat_id, msg)


async def session_cancelled_notify(user: User, session: TrainingSession) -> None:
    if not user.telegram_chat_id:
        return
    msg = f"❌ האימון '{session.title}' ב-{_fmt_date(session.session_date)} בוטל על ידי המדריך."
    await send_to_user(user.telegram_chat_id, msg)


async def waitlist_promoted(user: User, session: TrainingSession, minutes: int) -> None:
    if not user.telegram_chat_id:
        return
    msg = (
        f"🎉 מקום התפנה ב'{session.title}' ב-{_fmt_date(session.session_date)}!\n"
        f"יש לך {minutes} דקות לאשר."
    )
    await send_to_user(user.telegram_chat_id, msg)


async def review_reminder(user: User, session: TrainingSession) -> None:
    if not user.telegram_chat_id:
        return
    msg = (
        f"⭐ איך היה האימון '{session.title}'?\n"
        f"לחץ לדירוג: {SERVER_BASE_URL}/#rate/{session.id}"
    )
    await send_to_user(user.telegram_chat_id, msg)


async def twofa_code(user: User, code: str) -> None:
    if not user.telegram_chat_id:
        return
    msg = f"🔐 קוד האימות שלך: {code}\nתקף ל-10 דקות."
    await send_to_user(user.telegram_chat_id, msg)


async def password_reset_code(user: User, code: str) -> None:
    if not user.telegram_chat_id:
        return
    msg = f"🔑 קוד איפוס סיסמה: {code}\nתקף ל-10 דקות.\nאם לא ביקשת זאת, התעלם."
    await send_to_user(user.telegram_chat_id, msg)


async def password_reset_done(user: User) -> None:
    if not user.telegram_chat_id:
        return
    await send_to_user(user.telegram_chat_id, "✅ הסיסמה שלך שונתה בהצלחה.")


async def account_blocked(user: User, reason: str) -> None:
    if not user.telegram_chat_id:
        return
    msg = f"⛔ חשבונך הוגבל.\nסיבה: {reason}\nפנה למדריך לפרטים."
    await send_to_user(user.telegram_chat_id, msg)


async def account_unblocked(user: User) -> None:
    if not user.telegram_chat_id:
        return
    await send_to_user(user.telegram_chat_id, "✅ הגבלת חשבונך הוסרה. תוכל להזמין אימונים שוב.")


async def twofa_enabled_msg(user: User) -> None:
    if not user.telegram_chat_id:
        return
    await send_to_user(user.telegram_chat_id, "🔒 אימות דו-שלבי הופעל בהצלחה.")


async def twofa_disabled_msg(user: User) -> None:
    if not user.telegram_chat_id:
        return
    await send_to_user(user.telegram_chat_id, "🔓 אימות דו-שלבי כובה בחשבונך.")
