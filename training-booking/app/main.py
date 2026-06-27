import os
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.database import engine, get_db, SessionLocal
from app import models
from app.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    models.Base.metadata.create_all(bind=engine)

    # Ensure dirs
    for d in ["uploads/logo", "uploads/sessions", "static/icons"]:
        os.makedirs(d, exist_ok=True)

    # Generate placeholder PWA icons
    _generate_pwa_icons()

    # Seed admin user
    _seed_admin()

    # Seed SiteSettings row
    _seed_settings()

    # Register Telegram webhook
    server_url = os.getenv("SERVER_BASE_URL", "")
    if server_url:
        from app.services.telegram import set_webhook
        await set_webhook(f"{server_url}/api/telegram/webhook")

    # Start scheduler
    scheduler = create_scheduler()
    scheduler.start()

    yield

    scheduler.shutdown()


def _generate_pwa_icons():
    try:
        from PIL import Image, ImageDraw, ImageFont
        for size in [192, 512]:
            path = f"static/icons/icon-{size}.png"
            if not os.path.exists(path):
                img = Image.new("RGB", (size, size), color="#2563eb")
                draw = ImageDraw.Draw(img)
                font_size = size // 3
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()
                draw.text((size // 2, size // 2), "T", fill="white", font=font, anchor="mm")
                img.save(path)
    except Exception:
        pass


def _seed_admin():
    from sqlalchemy import select
    from app.models import User
    from app.auth import hash_password
    db = SessionLocal()
    try:
        admin = db.execute(select(User).where(User.role == "admin")).scalar_one_or_none()
        if not admin:
            phone = os.getenv("ADMIN_PHONE", "0500000000")
            password = os.getenv("ADMIN_PASSWORD", "admin123")
            first_name = os.getenv("ADMIN_FIRST_NAME", "מדריך")
            last_name = os.getenv("ADMIN_LAST_NAME", "ראשי")
            user = User(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                hashed_password=hash_password(password),
                role="admin",
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


def _seed_settings():
    from sqlalchemy import select
    from app.models import SiteSettings
    db = SessionLocal()
    try:
        settings = db.execute(select(SiteSettings).where(SiteSettings.id == 1)).scalar_one_or_none()
        if not settings:
            settings = SiteSettings(id=1)
            db.add(settings)
            db.commit()
    finally:
        db.close()


app = FastAPI(title="Training Booking", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Public endpoints: always add CORS header explicitly
@app.middleware("http")
async def add_public_cors(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/public"):
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# Register routers
from app.routers import (
    auth, users, telegram_connect, activity_types, blocked_dates,
    user_groups, sessions, bookings, waitlist, reviews, analytics,
    broadcast, settings, audit_log, public, admin_users
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(telegram_connect.router)
app.include_router(activity_types.router)
app.include_router(blocked_dates.router)
app.include_router(user_groups.router)
app.include_router(sessions.router)
app.include_router(bookings.router)
app.include_router(waitlist.router)
app.include_router(reviews.router)
app.include_router(analytics.router)
app.include_router(broadcast.router)
app.include_router(settings.router)
app.include_router(audit_log.router)
app.include_router(public.router)
app.include_router(admin_users.router)

# Static files — ensure uploads dir exists before mounting
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("uploads/") or full_path.startswith("static/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return FileResponse("static/index.html")
