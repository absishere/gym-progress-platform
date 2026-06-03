from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

try:
    from .database import Base, engine, get_db
    from .models import (
        Branch, Gym, LoginFailure, Member, Plan, Progress, Reminder, SessionToken,
        PlatformAdmin, PlatformSession, TrainerMemberAssignment, User, UserBranchAccess, WhatsAppConnection,
    )
    from .secrets_store import decrypt_secret, encrypt_secret
except ImportError:
    from database import Base, engine, get_db
    from models import (
        Branch, Gym, LoginFailure, Member, Plan, Progress, Reminder, SessionToken,
        PlatformAdmin, PlatformSession, TrainerMemberAssignment, User, UserBranchAccess, WhatsAppConnection,
    )
    from secrets_store import decrypt_secret, encrypt_secret


APP_ENV = os.getenv("GYM_APP_ENV", "development").lower()
SESSION_DAYS = int(os.getenv("GYM_SESSION_DAYS", "30"))
LOGIN_WINDOW_MINUTES = int(os.getenv("GYM_LOGIN_WINDOW_MINUTES", "15"))
LOGIN_MAX_FAILURES = int(os.getenv("GYM_LOGIN_MAX_FAILURES", "5"))
PUBLIC_SIGNUP_ENABLED = os.getenv("GYM_PUBLIC_SIGNUP_ENABLED", "false").lower() == "true"
CORS_ORIGINS = [value.strip().rstrip("/") for value in os.getenv("GYM_CORS_ORIGINS", "").split(",") if value.strip()]
if APP_ENV != "production":
    CORS_ORIGINS = sorted({*CORS_ORIGINS, "http://localhost:5173", "http://127.0.0.1:5173"})
elif not CORS_ORIGINS:
    raise RuntimeError("GYM_CORS_ORIGINS is required in production")
ALLOWED_HOSTS = [value.strip() for value in os.getenv("GYM_ALLOWED_HOSTS", "*").split(",") if value.strip()]
Goal = Literal["lose-weight", "build-muscle", "get-lean"]
UserRole = Literal["gym_owner", "staff", "trainer", "member"]


class GymSignup(BaseModel):
    gym_name: str = Field(min_length=2, max_length=100)
    owner_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    branches: list[str] = Field(min_length=1, max_length=25)


class PlatformLoginRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class PlatformGymCreate(BaseModel):
    gym_name: str = Field(min_length=2, max_length=100)
    owner_name: str = Field(min_length=2, max_length=80)
    owner_phone: str = Field(min_length=8, max_length=20)
    temporary_password: str = Field(min_length=8, max_length=128)
    branches: list[str] = Field(min_length=1, max_length=25)
    multi_branch_enabled: bool = False
    account_status: Literal["active", "suspended"] = "active"


class PlatformGymUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    account_status: Literal["active", "suspended"] | None = None
    multi_branch_enabled: bool | None = None
    owner_name: str | None = Field(default=None, min_length=2, max_length=80)
    owner_phone: str | None = Field(default=None, min_length=8, max_length=20)
    owner_temporary_password: str | None = Field(default=None, min_length=8, max_length=128)


class LoginRequest(BaseModel):
    workspace_slug: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class BranchSelection(BaseModel):
    branch_id: int


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserProvision(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    role: Literal["staff", "trainer"]
    branch_ids: list[int] = Field(min_length=1)
    temporary_password: str = Field(min_length=8, max_length=128)


class TrainerAssignment(BaseModel):
    member_id: int


class WhatsAppConnectionUpdate(BaseModel):
    business_account_id: str = Field(min_length=1, max_length=100)
    phone_number_id: str = Field(min_length=1, max_length=100)
    display_phone_number: str = Field(min_length=8, max_length=30)
    renewal_template_name: str = Field(default="membership_renewal_reminder", min_length=1, max_length=120)
    access_token: str = Field(min_length=1)
    app_secret: str = Field(min_length=1)


class MemberCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    email: str = Field(default="", max_length=120)
    package: str = Field(min_length=2, max_length=80)
    expires_on: date


class PlanRequest(BaseModel):
    member_id: int
    weight_kg: float = Field(gt=30, lt=300)
    height_cm: float = Field(gt=120, lt=250)
    age: int = Field(gt=12, lt=100)
    goal: Goal


class ProgressCreate(BaseModel):
    weight_kg: float = Field(gt=30, lt=300)
    recorded_on: date = Field(default_factory=date.today)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_phone(phone: str) -> str:
    value = re.sub(r"\D", "", phone)
    if len(value) < 8:
        raise HTTPException(status_code=422, detail="Enter a valid phone number")
    return value


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "gym"


def unique_workspace_slug(db: Session, gym_name: str) -> str:
    base, slug, suffix = slugify(gym_name), slugify(gym_name), 2
    while db.scalar(select(Gym.id).where(Gym.workspace_slug == slug)):
        slug, suffix = f"{base}-{suffix}", suffix + 1
    return slug


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$", 3)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(digest.hex(), expected)
    except (TypeError, ValueError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def branch_payload(branch: Branch) -> dict:
    return {"id": branch.id, "name": branch.name}


def user_payload(db: Session, user: User, active_branch_id: int | None = None) -> dict:
    branches = db.scalars(select(Branch).join(UserBranchAccess).where(UserBranchAccess.user_id == user.id).order_by(Branch.name)).all()
    return {"id": user.id, "name": user.name, "phone": user.phone, "role": user.role, "gym_id": user.gym_id, "must_change_password": user.must_change_password, "active_branch_id": active_branch_id, "branches": [branch_payload(branch) for branch in branches]}


def create_session(db: Session, user_id: int, branch_id: int) -> str:
    token, now = secrets.token_urlsafe(32), utc_now()
    db.execute(delete(SessionToken).where(SessionToken.expires_at <= now))
    db.add(SessionToken(token=hash_session_token(token), user_id=user_id, active_branch_id=branch_id, created_at=now, expires_at=now + timedelta(days=SESSION_DAYS)))
    return token


def create_platform_session(db: Session, admin_id: int) -> str:
    token, now = secrets.token_urlsafe(32), utc_now()
    db.execute(delete(PlatformSession).where(PlatformSession.expires_at <= now))
    db.add(PlatformSession(token=hash_session_token(token), admin_id=admin_id, created_at=now, expires_at=now + timedelta(days=SESSION_DAYS)))
    return token


def enforce_login_rate_limit(db: Session, slug: str, phone: str) -> None:
    cutoff = utc_now() - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    db.execute(delete(LoginFailure).where(LoginFailure.attempted_at <= cutoff))
    failures = db.scalar(select(func.count()).select_from(LoginFailure).where(LoginFailure.workspace_slug == slug, LoginFailure.phone == phone))
    if failures >= LOGIN_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many failed login attempts. Try again later.", headers={"Retry-After": str(LOGIN_WINDOW_MINUTES * 60)})


def get_current_session(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    with get_db() as db:
        row = db.scalar(select(SessionToken).where(SessionToken.token == hash_session_token(authorization.removeprefix("Bearer ").strip())))
        if row is None or row.expires_at.replace(tzinfo=timezone.utc) <= utc_now():
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        user = db.get(User, row.user_id)
        access = db.get(UserBranchAccess, (row.user_id, row.active_branch_id))
        if user is None or not user.is_active or access is None:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        gym = db.get(Gym, user.gym_id)
        if gym is None or gym.account_status != "active":
            raise HTTPException(status_code=403, detail="Gym access is not active")
        return {"token": row.token, "user_id": user.id, "gym_id": user.gym_id, "role": user.role, "active_branch_id": row.active_branch_id}


def get_platform_session(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Platform authentication required")
    with get_db() as db:
        row = db.scalar(select(PlatformSession).where(PlatformSession.token == hash_session_token(authorization.removeprefix("Bearer ").strip())))
        if row is None or row.expires_at.replace(tzinfo=timezone.utc) <= utc_now():
            raise HTTPException(status_code=401, detail="Platform session expired or invalid")
        admin = db.get(PlatformAdmin, row.admin_id)
        if admin is None or not admin.is_active:
            raise HTTPException(status_code=401, detail="Platform session expired or invalid")
        return {"token": row.token, "admin_id": admin.id, "phone": admin.phone, "name": admin.name}


def require_roles(*roles: UserRole):
    def check(session: Annotated[dict, Depends(get_current_session)]) -> dict:
        if session["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return session
    return check


def init_database() -> None:
    if APP_ENV != "production":
        Base.metadata.create_all(engine)
    phone, password = os.getenv("GYM_PLATFORM_ADMIN_PHONE"), os.getenv("GYM_PLATFORM_ADMIN_PASSWORD")
    if phone and password:
        with get_db() as db:
            normalized = normalize_phone(phone)
            admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.phone == normalized))
            if admin is None:
                db.add(PlatformAdmin(name=os.getenv("GYM_PLATFORM_ADMIN_NAME", "Forge Admin"), phone=normalized, password_hash=hash_password(password), created_at=utc_now()))


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(title="Forge Gym Platform API", version="0.3.0", lifespan=lifespan, docs_url=None if APP_ENV == "production" else "/docs", redoc_url=None if APP_ENV == "production" else "/redoc")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["*"])


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "strict-origin-when-cross-origin"})
    return response


@app.post("/api/auth/signup", status_code=201)
def signup(request: GymSignup) -> dict:
    if not PUBLIC_SIGNUP_ENABLED:
        raise HTTPException(status_code=403, detail="Public signup is not enabled yet")
    return create_gym_workspace(request.gym_name, request.owner_name, request.phone, request.password, request.branches, "self_serve")


def create_gym_workspace(gym_name: str, owner_name: str, owner_phone: str, password: str, branch_names: list[str], sales_channel: str, account_status: str = "active", multi_branch_enabled: bool | None = None) -> dict:
    names = list(dict.fromkeys(name.strip() for name in branch_names if name.strip()))
    if not names:
        raise HTTPException(status_code=422, detail="Add at least one branch")
    with get_db() as db:
        now = utc_now()
        gym = Gym(name=gym_name.strip(), workspace_slug=unique_workspace_slug(db, gym_name), multi_branch_enabled=len(names) > 1 if multi_branch_enabled is None else multi_branch_enabled, account_status=account_status, sales_channel=sales_channel, created_at=now)
        db.add(gym); db.flush()
        branches = [Branch(gym_id=gym.id, name=name, created_at=now) for name in names]
        db.add_all(branches); db.flush()
        user = User(gym_id=gym.id, name=owner_name.strip(), phone=normalize_phone(owner_phone), password_hash=hash_password(password), role="gym_owner", must_change_password=True, created_at=now)
        db.add(user); db.flush()
        db.add_all([UserBranchAccess(user_id=user.id, branch_id=branch.id) for branch in branches])
        db.flush()
        token = create_session(db, user.id, branches[0].id)
        return {"token": token, "gym": {"id": gym.id, "name": gym.name, "workspace_slug": gym.workspace_slug, "multi_branch_enabled": gym.multi_branch_enabled}, "user": user_payload(db, user, branches[0].id)}


@app.post("/api/auth/login")
def login(request: LoginRequest) -> dict:
    slug, phone = request.workspace_slug.lower(), normalize_phone(request.phone)
    with get_db() as db:
        enforce_login_rate_limit(db, slug, phone)
        user = db.scalar(select(User).join(Gym).where(Gym.workspace_slug == slug, User.phone == phone))
        gym = db.scalar(select(Gym).where(Gym.workspace_slug == slug))
        if gym is not None and gym.account_status != "active":
            raise HTTPException(status_code=403, detail="Gym access is not active")
        if user is None or not user.is_active or not verify_password(request.password, user.password_hash):
            db.add(LoginFailure(workspace_slug=slug, phone=phone, attempted_at=utc_now())); db.commit()
            raise HTTPException(status_code=401, detail="Invalid workspace, phone number, or password")
        db.execute(delete(LoginFailure).where(LoginFailure.workspace_slug == slug, LoginFailure.phone == phone))
        branch_id = db.scalar(select(UserBranchAccess.branch_id).where(UserBranchAccess.user_id == user.id).order_by(UserBranchAccess.branch_id))
        if branch_id is None:
            raise HTTPException(status_code=403, detail="No branch access assigned")
        return {"token": create_session(db, user.id, branch_id), "user": user_payload(db, user, branch_id)}


@app.get("/api/auth/me")
def current_user(session: Annotated[dict, Depends(get_current_session)]) -> dict:
    with get_db() as db:
        user, gym = db.get(User, session["user_id"]), db.get(Gym, session["gym_id"])
        return {"gym": {"id": gym.id, "name": gym.name, "workspace_slug": gym.workspace_slug, "multi_branch_enabled": gym.multi_branch_enabled}, "user": user_payload(db, user, session["active_branch_id"])}


@app.post("/api/auth/select-branch")
def select_branch(request: BranchSelection, session: Annotated[dict, Depends(get_current_session)]) -> dict:
    with get_db() as db:
        access, branch = db.get(UserBranchAccess, (session["user_id"], request.branch_id)), db.get(Branch, request.branch_id)
        if access is None or branch is None:
            raise HTTPException(status_code=403, detail="Branch access denied")
        db.get(SessionToken, session["token"]).active_branch_id = request.branch_id
        return {"active_branch": branch_payload(branch)}


@app.post("/api/auth/change-password")
def change_password(request: PasswordChange, session: Annotated[dict, Depends(get_current_session)]) -> dict:
    with get_db() as db:
        user = db.get(User, session["user_id"])
        if not verify_password(request.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.password_hash, user.must_change_password = hash_password(request.new_password), False
    return {"status": "password-updated"}


@app.post("/api/auth/logout")
def logout(session: Annotated[dict, Depends(get_current_session)]) -> dict:
    with get_db() as db:
        db.execute(delete(SessionToken).where(SessionToken.token == session["token"]))
    return {"status": "logged-out"}


def require_member(db: Session, member_id: int, session: dict) -> Member:
    member = db.scalar(select(Member).join(Branch).where(Member.id == member_id, Member.branch_id == session["active_branch_id"], Branch.gym_id == session["gym_id"]))
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if session["role"] == "trainer" and db.get(TrainerMemberAssignment, (session["user_id"], member_id)) is None:
        raise HTTPException(status_code=403, detail="Trainer is not assigned to this member")
    return member


def member_payload(member: Member) -> dict:
    days = (member.expires_on - date.today()).days
    return {"id": member.id, "name": member.name, "phone": member.phone, "email": member.email, "package": member.package, "expires_on": member.expires_on.isoformat(), "joined_on": member.joined_on.isoformat(), "days_left": days, "status": "expired" if days < 0 else "expiring" if days <= 7 else "active"}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/members")
def list_members(session: Annotated[dict, Depends(require_roles("gym_owner", "staff", "trainer"))]) -> list[dict]:
    with get_db() as db:
        query = select(Member).where(Member.branch_id == session["active_branch_id"])
        if session["role"] == "trainer":
            query = query.join(TrainerMemberAssignment).where(TrainerMemberAssignment.trainer_user_id == session["user_id"])
        return [member_payload(member) for member in db.scalars(query.order_by(Member.expires_on)).all()]


@app.post("/api/members", status_code=201)
def create_member(request: MemberCreate, session: Annotated[dict, Depends(require_roles("gym_owner", "staff"))]) -> dict:
    with get_db() as db:
        member = Member(branch_id=session["active_branch_id"], name=request.name.strip(), phone=normalize_phone(request.phone), email=request.email.strip(), package=request.package.strip(), expires_on=request.expires_on, joined_on=date.today())
        db.add(member); db.flush()
        return member_payload(member)


@app.get("/api/members/expiring")
def list_expiring_members(session: Annotated[dict, Depends(require_roles("gym_owner", "staff"))]) -> list[dict]:
    with get_db() as db:
        members = db.scalars(select(Member).where(Member.branch_id == session["active_branch_id"], Member.expires_on.between(date.today(), date.today() + timedelta(days=7))).order_by(Member.expires_on)).all()
        return [member_payload(member) for member in members]


def queue_reminder(member_id: int, session: dict) -> dict:
    with get_db() as db:
        member = require_member(db, member_id, session)
        row = Reminder(member_id=member.id, sent_at=utc_now(), channel="whatsapp", status="queued-demo")
        db.add(row)
        return {"member_id": member.id, "member_name": member.name, "channel": row.channel, "status": row.status, "message": f"Renewal reminder queued for {member.name}."}


@app.post("/api/reminders/expiring")
def send_expiring_reminders(session: Annotated[dict, Depends(require_roles("gym_owner", "staff"))]) -> dict:
    members = list_expiring_members(session)
    for member in members:
        queue_reminder(member["id"], session)
    return {"queued": len(members), "channel": "whatsapp", "status": "queued-demo"}


@app.post("/api/reminders/{member_id}")
def send_reminder(member_id: int, session: Annotated[dict, Depends(require_roles("gym_owner", "staff"))]) -> dict:
    return queue_reminder(member_id, session)


def build_plan(weight_kg: float, height_cm: float, age: int, goal: Goal) -> dict:
    config = {"lose-weight": ("Lose weight", 24, 1.7, "steady fat loss"), "build-muscle": ("Build muscle", 34, 2.0, "progressive strength"), "get-lean": ("Get lean", 28, 1.9, "body recomposition")}[goal]
    calories, protein = round(weight_kg * config[1] / 50) * 50, round(weight_kg * config[2])
    meals = [{"time": "07:30", "name": "Protein-first breakfast", "detail": "Eggs or paneer, oats, seasonal fruit", "calories": round(calories * .24)}, {"time": "12:45", "name": "Balanced lunch", "detail": "Lean protein, rice or roti, vegetables, curd", "calories": round(calories * .34)}, {"time": "16:30", "name": "Training snack", "detail": "Fruit, yogurt, and nuts", "calories": round(calories * .14)}, {"time": "20:00", "name": "Recovery dinner", "detail": "Protein, vegetables, and lighter carbs", "calories": round(calories * .28)}]
    workouts = [{"week": i, "theme": theme, "sessions": ["Full body strength", "Cardio + mobility", "Upper body + core", "Lower body strength"], "target": target} for i, theme, target in [(1, "Build the base", "Move with control."), (2, "Add volume", "Add one working set."), (3, "Progressive push", "Increase load slightly."), (4, "Consolidate", "Repeat with clean reps.")]]
    return {"goal": goal, "goal_label": config[0], "focus": config[3], "daily_calories": calories, "daily_protein_g": protein, "water_liters": round(max(2.2, weight_kg * .035), 1), "bmi": round(weight_kg / ((height_cm / 100) ** 2), 1), "age": age, "meals": meals, "workouts": workouts, "note": "General fitness guidance. Adjust with a qualified coach for injuries or medical needs."}


@app.post("/api/plans/generate")
def generate_plan(request: PlanRequest, session: Annotated[dict, Depends(require_roles("gym_owner", "staff", "trainer"))]) -> dict:
    with get_db() as db:
        require_member(db, request.member_id, session)
        payload = build_plan(request.weight_kg, request.height_cm, request.age, request.goal)
        plan = db.get(Plan, request.member_id) or Plan(member_id=request.member_id)
        plan.payload, plan.generated_on = json.dumps(payload), date.today(); db.add(plan)
        return payload


@app.get("/api/plans/{member_id}")
def get_plan(member_id: int, session: Annotated[dict, Depends(require_roles("gym_owner", "staff", "trainer"))]) -> dict:
    with get_db() as db:
        require_member(db, member_id, session); plan = db.get(Plan, member_id)
        if plan is None: raise HTTPException(status_code=404, detail="Plan not generated yet")
        return json.loads(plan.payload)


@app.get("/api/progress/{member_id}")
def list_progress(member_id: int, session: Annotated[dict, Depends(require_roles("gym_owner", "staff", "trainer"))]) -> list[dict]:
    with get_db() as db:
        require_member(db, member_id, session)
        return [{"id": row.id, "weight_kg": row.weight_kg, "recorded_on": row.recorded_on.isoformat()} for row in db.scalars(select(Progress).where(Progress.member_id == member_id).order_by(Progress.recorded_on)).all()]


@app.post("/api/progress/{member_id}", status_code=201)
def add_progress(member_id: int, request: ProgressCreate, session: Annotated[dict, Depends(require_roles("gym_owner", "staff", "trainer"))]) -> dict:
    with get_db() as db:
        require_member(db, member_id, session); row = Progress(member_id=member_id, weight_kg=request.weight_kg, recorded_on=request.recorded_on); db.add(row); db.flush()
        return {"id": row.id, "member_id": member_id, "weight_kg": row.weight_kg, "recorded_on": row.recorded_on.isoformat()}


@app.get("/api/dashboard/summary")
def dashboard_summary(session: Annotated[dict, Depends(require_roles("gym_owner", "staff", "trainer"))]) -> dict:
    members = list_members(session); branch_id = session["active_branch_id"]
    active = sum(m["days_left"] >= 0 for m in members)
    expiring = [m for m in members if 0 <= m["days_left"] <= 7]
    expired = sum(m["days_left"] < 0 for m in members)
    with get_db() as db:
        branch = db.get(Branch, branch_id)
        reminder_count = db.scalar(select(func.count()).select_from(Reminder).join(Member).where(Member.branch_id == branch_id, Reminder.sent_at >= utc_now() - timedelta(days=7)))
        whatsapp = db.get(WhatsAppConnection, session["gym_id"])
    if expiring:
        title = f"{len(expiring)} member{'s' if len(expiring) != 1 else ''} need renewal follow-up this week."
        detail = "WhatsApp is connected, so you can queue reminders now." if whatsapp and whatsapp.status == "connected" else "Connect WhatsApp before sending real reminders from Forge."
    elif expired:
        title = f"{expired} expired membership{'s' if expired != 1 else ''} need recovery follow-up."
        detail = "Start with recently expired members before adding new acquisition work."
    else:
        title = "No urgent renewal risk in the next 7 days."
        detail = "The insight will update as members approach expiry or payment records are added."
    return {
        "branch": branch_payload(branch),
        "members": {"total": len(members), "active": active, "expiring_this_week": len(expiring), "expired": expired},
        "retention": {"reminders_sent_last_7_days": reminder_count or 0},
        "revenue": {"monthly": None, "renewal_rate": None, "note": "Revenue and renewal rate need payment records; Forge is not estimating them."},
        "insight": {"title": title, "detail": detail, "action_enabled": bool(expiring), "expiring_member_ids": [member["id"] for member in expiring]},
    }


@app.post("/api/platform/auth/login")
def platform_login(request: PlatformLoginRequest) -> dict:
    with get_db() as db:
        admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.phone == normalize_phone(request.phone)))
        if admin is None or not admin.is_active or not verify_password(request.password, admin.password_hash):
            raise HTTPException(status_code=401, detail="Invalid platform credentials")
        return {"token": create_platform_session(db, admin.id), "admin": {"id": admin.id, "name": admin.name, "phone": admin.phone}}


@app.get("/api/platform/auth/me")
def platform_me(session: Annotated[dict, Depends(get_platform_session)]) -> dict:
    return {"admin": {"id": session["admin_id"], "name": session["name"], "phone": session["phone"]}}


@app.post("/api/platform/auth/logout")
def platform_logout(session: Annotated[dict, Depends(get_platform_session)]) -> dict:
    with get_db() as db:
        db.execute(delete(PlatformSession).where(PlatformSession.token == session["token"]))
    return {"status": "logged-out"}


def platform_gym_payload(db: Session, gym: Gym) -> dict:
    owners = db.scalars(select(User).where(User.gym_id == gym.id, User.role == "gym_owner").order_by(User.id)).all()
    branches = db.scalars(select(Branch).where(Branch.gym_id == gym.id).order_by(Branch.name)).all()
    return {
        "id": gym.id,
        "name": gym.name,
        "workspace_slug": gym.workspace_slug,
        "account_status": gym.account_status,
        "sales_channel": gym.sales_channel,
        "multi_branch_enabled": gym.multi_branch_enabled,
        "branches": [branch_payload(branch) for branch in branches],
        "owners": [{"id": owner.id, "name": owner.name, "phone": owner.phone, "is_active": owner.is_active} for owner in owners],
    }


@app.get("/api/platform/gyms")
def platform_list_gyms(_: Annotated[dict, Depends(get_platform_session)]) -> list[dict]:
    with get_db() as db:
        return [platform_gym_payload(db, gym) for gym in db.scalars(select(Gym).order_by(Gym.created_at.desc())).all()]


@app.post("/api/platform/gyms", status_code=201)
def platform_create_gym(request: PlatformGymCreate, _: Annotated[dict, Depends(get_platform_session)]) -> dict:
    payload = create_gym_workspace(request.gym_name, request.owner_name, request.owner_phone, request.temporary_password, request.branches, "direct", request.account_status, request.multi_branch_enabled)
    with get_db() as db:
        return platform_gym_payload(db, db.get(Gym, payload["gym"]["id"]))


@app.patch("/api/platform/gyms/{gym_id}")
def platform_update_gym(gym_id: int, request: PlatformGymUpdate, _: Annotated[dict, Depends(get_platform_session)]) -> dict:
    with get_db() as db:
        gym = db.get(Gym, gym_id)
        if gym is None:
            raise HTTPException(status_code=404, detail="Gym not found")
        if request.name is not None:
            gym.name = request.name.strip()
        if request.account_status is not None:
            gym.account_status = request.account_status
        if request.multi_branch_enabled is not None:
            gym.multi_branch_enabled = request.multi_branch_enabled
        owner = db.scalar(select(User).where(User.gym_id == gym.id, User.role == "gym_owner").order_by(User.id))
        if owner is not None:
            if request.owner_name is not None:
                owner.name = request.owner_name.strip()
            if request.owner_phone is not None:
                owner.phone = normalize_phone(request.owner_phone)
            if request.owner_temporary_password is not None:
                owner.password_hash = hash_password(request.owner_temporary_password)
                owner.must_change_password = True
        db.flush()
        return platform_gym_payload(db, gym)


@app.delete("/api/platform/gyms/{gym_id}")
def platform_delete_gym(gym_id: int, _: Annotated[dict, Depends(get_platform_session)]) -> dict:
    with get_db() as db:
        gym = db.get(Gym, gym_id)
        if gym is None:
            raise HTTPException(status_code=404, detail="Gym not found")
        db.delete(gym)
    return {"status": "deleted"}


@app.get("/api/access/users")
def list_users(session: Annotated[dict, Depends(require_roles("gym_owner"))]) -> list[dict]:
    with get_db() as db: return [user_payload(db, user) for user in db.scalars(select(User).where(User.gym_id == session["gym_id"]).order_by(User.role, User.name)).all()]


@app.post("/api/access/users", status_code=201)
def provision_user(request: UserProvision, session: Annotated[dict, Depends(require_roles("gym_owner"))]) -> dict:
    with get_db() as db:
        branch_ids = list(dict.fromkeys(request.branch_ids))
        if len(db.scalars(select(Branch).where(Branch.gym_id == session["gym_id"], Branch.id.in_(branch_ids))).all()) != len(branch_ids): raise HTTPException(status_code=422, detail="Every branch must belong to your gym")
        user = User(gym_id=session["gym_id"], name=request.name.strip(), phone=normalize_phone(request.phone), password_hash=hash_password(request.temporary_password), role=request.role, must_change_password=True, created_at=utc_now())
        db.add(user)
        try: db.flush()
        except IntegrityError as error: raise HTTPException(status_code=409, detail="This phone number already has access to the gym") from error
        db.add_all([UserBranchAccess(user_id=user.id, branch_id=branch_id) for branch_id in branch_ids])
        db.flush()
        return user_payload(db, user)


@app.post("/api/access/trainers/{trainer_id}/members", status_code=201)
def assign_trainer_member(trainer_id: int, request: TrainerAssignment, session: Annotated[dict, Depends(require_roles("gym_owner"))]) -> dict:
    with get_db() as db:
        trainer, member = db.get(User, trainer_id), db.get(Member, request.member_id)
        if trainer is None or trainer.gym_id != session["gym_id"] or trainer.role != "trainer" or member is None: raise HTTPException(status_code=404, detail="Trainer or member not found")
        if db.get(UserBranchAccess, (trainer_id, member.branch_id)) is None: raise HTTPException(status_code=422, detail="Trainer must have access to the member's branch")
        db.merge(TrainerMemberAssignment(trainer_user_id=trainer_id, member_id=member.id, created_at=utc_now()))
        return {"trainer_user_id": trainer_id, "member_id": member.id}


def whatsapp_payload(row: WhatsAppConnection | None) -> dict:
    return {"connected": bool(row and row.status == "connected"), "status": row.status if row else "not-configured", "business_account_id": row.business_account_id if row else None, "phone_number_id": row.phone_number_id if row else None, "display_phone_number": row.display_phone_number if row else None, "renewal_template_name": row.renewal_template_name if row else None}


@app.get("/api/integrations/whatsapp")
def get_whatsapp(session: Annotated[dict, Depends(require_roles("gym_owner"))]) -> dict:
    with get_db() as db: return whatsapp_payload(db.get(WhatsAppConnection, session["gym_id"]))


@app.put("/api/integrations/whatsapp")
def put_whatsapp(request: WhatsAppConnectionUpdate, session: Annotated[dict, Depends(require_roles("gym_owner"))]) -> dict:
    with get_db() as db:
        row = db.get(WhatsAppConnection, session["gym_id"]) or WhatsAppConnection(gym_id=session["gym_id"])
        row.business_account_id, row.phone_number_id, row.display_phone_number, row.renewal_template_name = request.business_account_id.strip(), request.phone_number_id.strip(), request.display_phone_number.strip(), request.renewal_template_name.strip()
        row.encrypted_access_token, row.encrypted_app_secret, row.status, row.updated_at = encrypt_secret(request.access_token), encrypt_secret(request.app_secret), "pending-verification", utc_now()
        db.add(row); db.flush()
        decrypt_secret(row.encrypted_access_token)
        return whatsapp_payload(row)
