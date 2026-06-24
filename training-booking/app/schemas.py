from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, field_validator, ConfigDict


class UserBase(BaseModel):
    first_name: str
    last_name: str
    phone: str


class UserRegister(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    phone: str
    password: str


class UserOut(UserBase):
    model_config = {"from_attributes": True}
    id: int
    role: str
    telegram_chat_id: Optional[str] = None
    twofa_enabled: bool
    is_blocked: bool
    created_at: datetime


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int
    token_version: int
    twofa_pending: bool = False


class TwoFAVerify(BaseModel):
    temp_token: str
    code: str


class ForgotPassword(BaseModel):
    phone: str


class ResetPassword(BaseModel):
    phone: str
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class ActivityTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class ActivityTypeCreate(ActivityTypeBase):
    pass


class ActivityTypeUpdate(ActivityTypeBase):
    pass


class ActivityTypeOut(ActivityTypeBase):
    model_config = {"from_attributes": True}
    id: int
    created_at: datetime


class BlockedDateCreate(BaseModel):
    date: str
    label: str


class BlockedDateOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    date: str
    label: str
    created_at: datetime


class UserGroupBase(BaseModel):
    name: str
    description: Optional[str] = None


class UserGroupCreate(UserGroupBase):
    pass


class UserGroupUpdate(UserGroupBase):
    pass


class UserGroupOut(UserGroupBase):
    model_config = {"from_attributes": True}
    id: int
    created_at: datetime


class UserGroupMemberOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    user_id: int
    first_name: str
    last_name: str
    phone: str
    added_at: datetime


class SessionBase(BaseModel):
    title: str
    description: Optional[str] = None
    activity_type_id: Optional[int] = None
    instructor_id: Optional[int] = None
    session_date: datetime
    max_participants: int
    location: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    requirements: Optional[str] = None
    online_link: Optional[str] = None


class SessionCreate(SessionBase):
    recurring_freq: Optional[str] = None
    recurring_until: Optional[datetime] = None
    allowed_group_ids: List[int] = []


class SessionUpdate(SessionBase):
    allowed_group_ids: Optional[List[int]] = None


class ActivityTypeSmall(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str


class InstructorSmall(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    first_name: str
    last_name: str


class SessionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    title: str
    description: Optional[str] = None
    activity_type_id: Optional[int] = None
    activity_type: Optional[ActivityTypeSmall] = None
    instructor_id: Optional[int] = None
    instructor: Optional[InstructorSmall] = None
    session_date: datetime
    max_participants: int
    location: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    requirements: Optional[str] = None
    cover_image_filename: Optional[str] = None
    online_link: Optional[str] = None
    is_cancelled: bool
    recurring_group_id: Optional[str] = None
    created_at: datetime
    booking_count: int = 0
    avg_rating: Optional[float] = None
    google_calendar_url: Optional[str] = None
    is_restricted: bool = False


class BookingCreate(BaseModel):
    session_id: int


class BookingOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    session_id: int
    user_id: int
    booked_at: datetime
    attended: Optional[bool] = None
    session: Optional[SessionOut] = None


class WaitlistCreate(BaseModel):
    session_id: int


class WaitlistOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    session_id: int
    user_id: int
    joined_at: datetime
    status: str
    expires_at: Optional[datetime] = None


class ReviewCreate(BaseModel):
    stars: int
    comment: Optional[str] = None

    @field_validator("stars")
    @classmethod
    def stars_range(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Stars must be between 1 and 5")
        return v

    @field_validator("comment")
    @classmethod
    def comment_max(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            raise ValueError("Comment must be at most 500 characters")
        return v


class ReviewOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    user_id: int
    session_id: int
    stars: int
    comment: Optional[str] = None
    created_at: datetime
    user: Optional[UserBase] = None


class SiteSettingsUpdate(BaseModel):
    app_name: Optional[str] = None
    primary_color: Optional[str] = None
    cancel_hours_limit: Optional[int] = None
    waitlist_hold_minutes: Optional[int] = None
    support_telegram_username: Optional[str] = None


class SiteSettingsOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    logo_filename: Optional[str] = None
    app_name: str
    primary_color: str
    cancel_hours_limit: int
    waitlist_hold_minutes: int
    support_telegram_username: Optional[str] = None
    updated_at: datetime


class AuditLogOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    actor_id: Optional[int] = None
    actor_name: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_label: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


class BroadcastRequest(BaseModel):
    message: str
    confirm: bool = False


class BlockUserRequest(BaseModel):
    reason: str


class AttendanceUpdate(BaseModel):
    attended: bool


class TwoFACodeRequest(BaseModel):
    code: str


class AdminUserOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    first_name: str
    last_name: str
    phone: str
    role: str
    telegram_chat_id: Optional[str] = None
    twofa_enabled: bool
    is_blocked: bool
    block_reason: Optional[str] = None
    blocked_at: Optional[datetime] = None
    created_at: datetime
