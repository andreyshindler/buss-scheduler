import os
import uuid
import shutil
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import SiteSettings, User
from app.schemas import SiteSettingsUpdate, SiteSettingsOut
from app.auth import require_admin
from app.services import audit

router = APIRouter(prefix="/api/settings", tags=["settings"])
LOGO_DIR = "uploads/logo"


def _get_or_create_settings(db: Session) -> SiteSettings:
    settings = db.execute(select(SiteSettings).where(SiteSettings.id == 1)).scalar_one_or_none()
    if not settings:
        settings = SiteSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/config", response_model=SiteSettingsOut)
async def get_config(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return _get_or_create_settings(db)


@router.put("/config", response_model=SiteSettingsOut)
async def update_config(data: SiteSettingsUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    settings = _get_or_create_settings(db)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(settings, k, v)
    db.commit()
    db.refresh(settings)
    await audit.log(db, current_user, "admin.settings_updated", request=request)
    return settings


@router.get("/logo")
async def get_logo(db: Session = Depends(get_db)):
    settings = _get_or_create_settings(db)
    return {"logo_filename": settings.logo_filename}


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if file.size and file.size > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")
    allowed = {"image/jpeg", "image/png", "image/svg+xml", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Invalid file type")

    os.makedirs(LOGO_DIR, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "png"
    filename = f"logo-{uuid.uuid4()}.{ext}"
    filepath = os.path.join(LOGO_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    settings = _get_or_create_settings(db)
    if settings.logo_filename:
        old = os.path.join(LOGO_DIR, settings.logo_filename)
        if os.path.exists(old):
            os.remove(old)
    settings.logo_filename = filename
    db.commit()
    await audit.log(db, current_user, "admin.logo_uploaded")
    return {"filename": filename}


@router.delete("/logo")
async def delete_logo(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    settings = _get_or_create_settings(db)
    if settings.logo_filename:
        filepath = os.path.join(LOGO_DIR, settings.logo_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    settings.logo_filename = None
    db.commit()
    await audit.log(db, current_user, "admin.logo_removed")
    return {"detail": "Logo removed"}
