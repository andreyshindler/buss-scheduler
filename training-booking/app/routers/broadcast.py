from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.schemas import BroadcastRequest
from app.auth import require_admin
from app.services import audit
from app.services.telegram import send_to_user

router = APIRouter(prefix="/api/admin", tags=["broadcast"])


async def _do_broadcast(users: list, message: str):
    for user in users:
        if user.telegram_chat_id:
            await send_to_user(user.telegram_chat_id, message)


@router.post("/broadcast")
async def broadcast(data: BroadcastRequest, background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    users = db.execute(
        select(User).where(User.telegram_chat_id.isnot(None)).where(User.telegram_chat_id != "")
    ).scalars().all()
    count = len(users)

    if not data.confirm:
        return {"recipient_count": count}

    background_tasks.add_task(_do_broadcast, users, data.message)
    await audit.log(db, current_user, "admin.broadcast", details={"message": data.message[:100], "recipient_count": count}, request=request)
    return {"detail": f"Sending to {count} users", "recipient_count": count}
