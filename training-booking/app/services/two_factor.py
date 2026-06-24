import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import TwoFACode

# In-memory 2FA failure tracking: {user_id: (fail_count, lockout_until)}
_2fa_failures: dict[int, tuple[int, Optional[datetime]]] = {}


def generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def create_2fa_code(db: Session, user_id: int, purpose: str) -> str:
    code = generate_code()
    entry = TwoFACode(
        user_id=user_id,
        code=code,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(entry)
    db.commit()
    return code


def verify_2fa_code(db: Session, user_id: int, code: str, purpose: str) -> bool:
    now = datetime.now(timezone.utc)

    # Check lockout
    if user_id in _2fa_failures:
        fail_count, lockout_until = _2fa_failures[user_id]
        if lockout_until and now < lockout_until:
            return False

    stmt = (
        select(TwoFACode)
        .where(TwoFACode.user_id == user_id)
        .where(TwoFACode.code == code)
        .where(TwoFACode.purpose == purpose)
        .where(TwoFACode.used == False)
        .where(TwoFACode.expires_at > now)
        .order_by(TwoFACode.created_at.desc())
    )
    entry = db.execute(stmt).scalar_one_or_none()
    if entry:
        entry.used = True
        db.commit()
        _2fa_failures.pop(user_id, None)
        return True

    # Record failure
    fail_count, _ = _2fa_failures.get(user_id, (0, None))
    fail_count += 1
    lockout_until = None
    if fail_count >= 5:
        lockout_until = now + timedelta(minutes=15)
        fail_count = 0
    _2fa_failures[user_id] = (fail_count, lockout_until)
    return False
