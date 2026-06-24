import os
import random
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models import User, PasswordResetRequest
from app.schemas import UserRegister, UserLogin, Token, TwoFAVerify, ForgotPassword, ResetPassword
from app.auth import hash_password, verify_password, create_access_token, decode_token, TEMP_TOKEN_EXPIRE_MINUTES
from app.services import audit, two_factor, notifications

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=Token)
async def register(data: UserRegister, request: Request, db: Session = Depends(get_db)):
    existing = db.execute(select(User).where(User.phone == data.phone)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")
    user = User(
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        hashed_password=hash_password(data.password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    await audit.log(db, user, "auth.register", "user", user.id, data.phone, request=request)
    token = create_access_token(user.id, user.token_version)
    return Token(access_token=token)


@router.post("/login")
async def login(data: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.phone == data.phone)).scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.is_blocked:
        raise HTTPException(status_code=403, detail="Account is blocked")

    if user.twofa_enabled:
        if not user.telegram_chat_id:
            raise HTTPException(status_code=400, detail="Connect Telegram first to use 2FA")
        code = two_factor.create_2fa_code(db, user.id, "login")
        await notifications.twofa_code(user, code)
        temp_token = create_access_token(user.id, user.token_version, twofa_pending=True, expires_minutes=TEMP_TOKEN_EXPIRE_MINUTES)
        await audit.log(db, user, "auth.login_2fa_sent", "user", user.id, user.phone, request=request)
        return {"requires_2fa": True, "temp_token": temp_token}

    await audit.log(db, user, "auth.login", "user", user.id, user.phone, request=request)
    token = create_access_token(user.id, user.token_version)
    return Token(access_token=token)


@router.post("/verify-2fa", response_model=Token)
async def verify_2fa(data: TwoFAVerify, request: Request, db: Session = Depends(get_db)):
    from jose import JWTError
    try:
        payload = decode_token(data.temp_token)
        if not payload.get("2fa_pending"):
            raise HTTPException(status_code=400, detail="Invalid token")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ok = two_factor.verify_2fa_code(db, user.id, data.code, "login")
    if not ok:
        await audit.log(db, user, "auth.2fa_failed", "user", user.id, user.phone, request=request)
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    await audit.log(db, user, "auth.2fa_verified", "user", user.id, user.phone, request=request)
    token = create_access_token(user.id, user.token_version)
    return Token(access_token=token)


@router.post("/forgot-password")
async def forgot_password(data: ForgotPassword, request: Request, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.phone == data.phone)).scalar_one_or_none()
    if user and user.telegram_chat_id:
        code = "".join(random.choices(string.digits, k=6))
        entry = PasswordResetRequest(
            user_id=user.id,
            code=code,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.add(entry)
        db.commit()
        await notifications.password_reset_code(user, code)
        await audit.log(db, user, "auth.password_reset_requested", "user", user.id, user.phone, request=request)
    return {"detail": "If this number is linked to Telegram, a code was sent"}


@router.post("/reset-password")
async def reset_password(data: ResetPassword, request: Request, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.phone == data.phone)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid code")

    now = datetime.now(timezone.utc)
    stmt = (
        select(PasswordResetRequest)
        .where(PasswordResetRequest.user_id == user.id)
        .where(PasswordResetRequest.code == data.code)
        .where(PasswordResetRequest.used == False)
        .where(PasswordResetRequest.expires_at > now)
        .order_by(PasswordResetRequest.created_at.desc())
    )
    entry = db.execute(stmt).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    entry.used = True
    user.hashed_password = hash_password(data.new_password)
    user.token_version += 1
    db.commit()
    await notifications.password_reset_done(user)
    await audit.log(db, user, "auth.password_reset_done", "user", user.id, user.phone, request=request)
    return {"detail": "Password changed successfully"}
