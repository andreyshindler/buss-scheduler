from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models import BlockedDate, User
from app.schemas import BlockedDateCreate, BlockedDateOut
from app.auth import require_admin_or_instructor
from app.services import audit

router = APIRouter(prefix="/api/blocked-dates", tags=["blocked-dates"])


@router.get("", response_model=list[BlockedDateOut])
async def list_blocked_dates(db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    rows = db.execute(select(BlockedDate).order_by(BlockedDate.date)).scalars().all()
    return rows


@router.post("", response_model=BlockedDateOut)
async def create_blocked_date(data: BlockedDateCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    existing = db.execute(select(BlockedDate).where(BlockedDate.date == data.date)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Date already blocked")
    bd = BlockedDate(date=data.date, label=data.label, created_by_id=current_user.id)
    db.add(bd)
    db.commit()
    db.refresh(bd)
    await audit.log(db, current_user, "admin.blocked_date_added", "blocked_date", bd.id, bd.date, request=request)
    return bd


@router.delete("/{bd_id}")
async def delete_blocked_date(bd_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    bd = db.execute(select(BlockedDate).where(BlockedDate.id == bd_id)).scalar_one_or_none()
    if not bd:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(bd)
    db.commit()
    return {"detail": "Deleted"}
