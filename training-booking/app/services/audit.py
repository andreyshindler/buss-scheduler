import json
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models import AuditLog, User


async def log(
    db: Session,
    actor: Optional[User],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_label: Optional[str] = None,
    details: Optional[Any] = None,
    request=None,
):
    try:
        actor_name = f"{actor.first_name} {actor.last_name}" if actor else "system"
        actor_id = actor.id if actor else None
        ip = None
        if request:
            forwarded = request.headers.get("X-Forwarded-For")
            ip = forwarded.split(",")[0].strip() if forwarded else getattr(request.client, "host", None)
        details_str = json.dumps(details, ensure_ascii=False) if details is not None else None
        entry = AuditLog(
            actor_id=actor_id,
            actor_name=actor_name,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            details=details_str,
            ip_address=ip,
        )
        db.add(entry)
        db.commit()
    except Exception:
        pass
