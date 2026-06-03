from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

try:
    from .database import Base
except ImportError:
    from database import Base


class Gym(Base):
    __tablename__ = "gyms"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    workspace_slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    multi_branch_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("gym_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    gym_id: Mapped[int] = mapped_column(ForeignKey("gyms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("gym_id", "phone"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    gym_id: Mapped[int] = mapped_column(ForeignKey("gyms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserBranchAccess(Base):
    __tablename__ = "user_branch_access"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True)


class SessionToken(Base):
    __tablename__ = "sessions"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    active_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoginFailure(Base):
    __tablename__ = "login_failures"
    __table_args__ = (Index("idx_login_failures_lookup", "workspace_slug", "phone", "attempted_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_slug: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WhatsAppConnection(Base):
    __tablename__ = "whatsapp_connections"
    gym_id: Mapped[int] = mapped_column(ForeignKey("gyms.id", ondelete="CASCADE"), primary_key=True)
    business_account_id: Mapped[str] = mapped_column(String(100))
    phone_number_id: Mapped[str] = mapped_column(String(100))
    display_phone_number: Mapped[str] = mapped_column(String(30))
    renewal_template_name: Mapped[str] = mapped_column(String(120))
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    encrypted_app_secret: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (Index("idx_members_branch_expiry", "branch_id", "expires_on"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(120), default="")
    package: Mapped[str] = mapped_column(String(80))
    expires_on: Mapped[Date] = mapped_column(Date)
    joined_on: Mapped[Date] = mapped_column(Date)


class TrainerMemberAssignment(Base):
    __tablename__ = "trainer_member_assignments"
    trainer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(40))


class Plan(Base):
    __tablename__ = "plans"
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    generated_on: Mapped[Date] = mapped_column(Date)


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (Index("idx_progress_member_date", "member_id", "recorded_on"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    weight_kg: Mapped[float] = mapped_column(Float)
    recorded_on: Mapped[Date] = mapped_column(Date)
