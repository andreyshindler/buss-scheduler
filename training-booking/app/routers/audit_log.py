from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import AuditLog, User
from app.auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["audit"])


@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action_type: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action_type and action_type != "all":
        if action_type == "bookings":
            stmt = stmt.where(AuditLog.action.like("booking.%"))
        elif action_type == "users":
            stmt = stmt.where(AuditLog.action.like("user.%") | AuditLog.action.like("auth.%"))
        elif action_type == "sessions":
            stmt = stmt.where(AuditLog.action.like("session.%"))
        elif action_type == "admin":
            stmt = stmt.where(AuditLog.action.like("admin.%"))
        else:
            stmt = stmt.where(AuditLog.action.like(f"{action_type}%"))
    if user_id:
        stmt = stmt.where(AuditLog.actor_id == user_id)
    if date_from:
        from datetime import datetime
        stmt = stmt.where(AuditLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        from datetime import datetime
        stmt = stmt.where(AuditLog.created_at <= datetime.fromisoformat(date_to))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    offset = (page - 1) * page_size
    rows = db.execute(stmt.offset(offset).limit(page_size)).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "actor_id": r.actor_id,
                "actor_name": r.actor_name,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "target_label": r.target_label,
                "details": r.details,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "pages": max(1, (total + page_size - 1) // page_size),
    }
