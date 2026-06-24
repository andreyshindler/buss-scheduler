from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models import ActivityType, TrainingSession
from app.schemas import ActivityTypeCreate, ActivityTypeUpdate, ActivityTypeOut
from app.auth import get_current_active_user, require_admin_or_instructor
from app.models import User
from app.services import audit

router = APIRouter(prefix="/api/activity-types", tags=["activity-types"])


@router.get("", response_model=list[ActivityTypeOut])
async def list_activity_types(db: Session = Depends(get_db)):
    rows = db.execute(select(ActivityType).where(ActivityType.is_active == True).order_by(ActivityType.sort_order, ActivityType.name)).scalars().all()
    return rows


@router.post("", response_model=ActivityTypeOut)
async def create_activity_type(data: ActivityTypeCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    at = ActivityType(**data.model_dump())
    db.add(at)
    db.commit()
    db.refresh(at)
    await audit.log(db, current_user, "admin.activity_type_created", "activity_type", at.id, at.name, request=request)
    return at


@router.put("/{at_id}", response_model=ActivityTypeOut)
async def update_activity_type(at_id: int, data: ActivityTypeUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    at = db.execute(select(ActivityType).where(ActivityType.id == at_id)).scalar_one_or_none()
    if not at:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in data.model_dump().items():
        setattr(at, k, v)
    db.commit()
    db.refresh(at)
    return at


@router.delete("/{at_id}")
async def delete_activity_type(at_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin_or_instructor)):
    at = db.execute(select(ActivityType).where(ActivityType.id == at_id)).scalar_one_or_none()
    if not at:
        raise HTTPException(status_code=404, detail="Not found")
    in_use = db.execute(select(TrainingSession).where(TrainingSession.activity_type_id == at_id)).first()
    if in_use:
        raise HTTPException(status_code=400, detail="Activity type is in use by sessions")
    db.delete(at)
    db.commit()
    return {"detail": "Deleted"}
