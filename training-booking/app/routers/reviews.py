from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import User, TrainingSession, Booking, Review
from app.schemas import ReviewCreate, ReviewOut
from app.auth import get_current_active_user

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/{session_id}")
async def create_review(session_id: int, data: ReviewCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    session = db.execute(select(TrainingSession).where(TrainingSession.id == session_id)).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.now(timezone.utc)
    session_dt = session.session_date
    if session_dt.tzinfo is None:
        session_dt = session_dt.replace(tzinfo=timezone.utc)
    if session_dt >= now:
        raise HTTPException(status_code=400, detail="Can only review past sessions")

    booking = db.execute(
        select(Booking).where(Booking.user_id == current_user.id).where(Booking.session_id == session_id)
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=403, detail="You must have a booking to review")

    existing = db.execute(
        select(Review).where(Review.user_id == current_user.id).where(Review.session_id == session_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Already reviewed")

    review = Review(user_id=current_user.id, session_id=session_id, stars=data.stars, comment=data.comment)
    db.add(review)
    db.commit()
    db.refresh(review)
    return {"detail": "Review submitted", "id": review.id}


@router.get("/{session_id}")
async def get_reviews(session_id: int, db: Session = Depends(get_db)):
    reviews = db.execute(
        select(Review).where(Review.session_id == session_id).order_by(Review.created_at.desc())
    ).scalars().all()
    avg = db.execute(select(func.avg(Review.stars)).where(Review.session_id == session_id)).scalar()
    return {
        "reviews": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "first_name": r.user.first_name,
                "stars": r.stars,
                "comment": r.comment,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
        "avg_rating": round(float(avg), 1) if avg else None,
        "count": len(reviews),
    }


@router.get("/my")
async def my_reviews(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    reviews = db.execute(
        select(Review).where(Review.user_id == current_user.id).order_by(Review.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "title": r.session.title,
            "stars": r.stars,
            "comment": r.comment,
            "created_at": r.created_at.isoformat(),
        }
        for r in reviews
    ]
