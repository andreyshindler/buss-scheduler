import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.auth import get_current_active_user
from app.services import audit

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")


@router.get("/link")
async def get_link(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    token = secrets.token_urlsafe(24)
    current_user.telegram_link_token = token
    current_user.telegram_link_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()
    link = f"https://t.me/{BOT_USERNAME}?start={token}" if BOT_USERNAME else f"?start={token}"
    return {"link": link, "token": token}


@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        message = body.get("message", {})
        chat = message.get("chat", {})
        text = message.get("text", "")
        chat_id = str(chat.get("id", ""))

        if text.startswith("/start "):
            token = text.split(" ", 1)[1].strip()
            now = datetime.now(timezone.utc)
            user = db.execute(
                select(User)
                .where(User.telegram_link_token == token)
                .where(User.telegram_link_token_expires > now)
            ).scalar_one_or_none()
            if user:
                user.telegram_chat_id = chat_id
                user.telegram_link_token = None
                user.telegram_link_token_expires = None
                db.commit()
                await audit.log(db, user, "user.telegram_connected", "user", user.id, user.phone)

                from app.services.telegram import send_to_user
                await send_to_user(chat_id, f"✅ חשבונך חובר לטלגרם בהצלחה!")
    except Exception:
        pass
    return {"ok": True}


@router.get("/status")
async def check_status(current_user: User = Depends(get_current_active_user)):
    return {"connected": bool(current_user.telegram_chat_id)}
