from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    telegram_link_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telegram_link_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    blocked_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    twofa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    blocked_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[blocked_by_id], remote_side="User.id")
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="user", foreign_keys="Booking.user_id")
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship("WaitlistEntry", back_populates="user")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="user")
    group_memberships: Mapped[list["UserGroupMembership"]] = relationship("UserGroupMembership", back_populates="user", foreign_keys="UserGroupMembership.user_id")


class UserGroup(Base):
    __tablename__ = "user_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    memberships: Mapped[list["UserGroupMembership"]] = relationship("UserGroupMembership", back_populates="group", cascade="all, delete-orphan")
    session_restrictions: Mapped[list["SessionGroupRestriction"]] = relationship("SessionGroupRestriction", back_populates="group")


class UserGroupMembership(Base):
    __tablename__ = "user_group_memberships"
    __table_args__ = (UniqueConstraint("user_id", "group_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("user_groups.id"))
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="group_memberships", foreign_keys=[user_id])
    group: Mapped["UserGroup"] = relationship("UserGroup", back_populates="memberships")
    added_by: Mapped["User"] = relationship("User", foreign_keys=[added_by_id])


class ActivityType(Base):
    __tablename__ = "activity_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    sessions: Mapped[list["TrainingSession"]] = relationship("TrainingSession", back_populates="activity_type")


class BlockedDate(Base):
    __tablename__ = "blocked_dates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(10), unique=True)  # YYYY-MM-DD
    label: Mapped[str] = mapped_column(String(200))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    created_by: Mapped["User"] = relationship("User")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activity_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("activity_types.id"), nullable=True)
    instructor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    session_date: Mapped[datetime] = mapped_column(DateTime)
    max_participants: Mapped[int] = mapped_column(Integer)
    location: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_image_filename: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    online_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    online_link_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring_group_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    activity_type: Mapped[Optional["ActivityType"]] = relationship("ActivityType", back_populates="sessions")
    instructor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[instructor_id])
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="session", cascade="all, delete-orphan")
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship("WaitlistEntry", back_populates="session", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="session", cascade="all, delete-orphan")
    group_restrictions: Mapped[list["SessionGroupRestriction"]] = relationship("SessionGroupRestriction", back_populates="session", cascade="all, delete-orphan")


class SessionGroupRestriction(Base):
    __tablename__ = "session_group_restrictions"
    __table_args__ = (UniqueConstraint("session_id", "group_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("user_groups.id"))

    session: Mapped["TrainingSession"] = relationship("TrainingSession", back_populates="group_restrictions")
    group: Mapped["UserGroup"] = relationship("UserGroup", back_populates="session_restrictions")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("user_id", "session_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id"))
    booked_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    attended: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="bookings", foreign_keys=[user_id])
    session: Mapped["TrainingSession"] = relationship("TrainingSession", back_populates="bookings")


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (UniqueConstraint("user_id", "session_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="waiting")

    user: Mapped["User"] = relationship("User", back_populates="waitlist_entries")
    session: Mapped["TrainingSession"] = relationship("TrainingSession", back_populates="waitlist_entries")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "session_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id"))
    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    session: Mapped["TrainingSession"] = relationship("TrainingSession", back_populates="reviews")


class TwoFACode(Base):
    __tablename__ = "twofa_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    code: Mapped[str] = mapped_column(String(6))
    purpose: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship("User")


class PasswordResetRequest(Base):
    __tablename__ = "password_reset_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    code: Mapped[str] = mapped_column(String(6))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    actor: Mapped[Optional["User"]] = relationship("User")


class SiteSettings(Base):
    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    logo_filename: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    app_name: Mapped[str] = mapped_column(String(100), default="Training Booking")
    primary_color: Mapped[str] = mapped_column(String(10), default="#2563eb")
    cancel_hours_limit: Mapped[int] = mapped_column(Integer, default=2)
    waitlist_hold_minutes: Mapped[int] = mapped_column(Integer, default=30)
    support_telegram_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
