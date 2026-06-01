from __future__ import annotations

import json
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("GYM_DATABASE_PATH", BASE_DIR / "gym_platform.db"))

Goal = Literal["lose-weight", "build-muscle", "get-lean"]
UserRole = Literal["gym_owner", "staff", "trainer", "member"]


class GymSignup(BaseModel):
    gym_name: str = Field(min_length=2, max_length=100)
    owner_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    branches: list[str] = Field(min_length=1, max_length=25)


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


class WhatsAppConnectionUpdate(BaseModel):
    business_account_id: str = Field(min_length=1, max_length=100)
    phone_number_id: str = Field(min_length=1, max_length=100)
    display_phone_number: str = Field(min_length=8, max_length=30)
    renewal_template_name: str = Field(default="membership_renewal_reminder", min_length=1, max_length=120)


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


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_demo_workspace(connection: sqlite3.Connection) -> int:
    now = utc_now().isoformat()
    gym = connection.execute("SELECT id FROM gyms WHERE workspace_slug = ?", ("forge-demo",)).fetchone()
    if gym is None:
        cursor = connection.execute(
            "INSERT INTO gyms (name, workspace_slug, multi_branch_enabled, created_at) VALUES (?, ?, ?, ?)",
            ("Forge Performance Club", "forge-demo", 0, now),
        )
        gym_id = cursor.lastrowid
    else:
        gym_id = gym["id"]
    branch = connection.execute(
        "SELECT id FROM branches WHERE gym_id = ? ORDER BY id LIMIT 1",
        (gym_id,),
    ).fetchone()
    if branch is None:
        cursor = connection.execute(
            "INSERT INTO branches (gym_id, name, created_at) VALUES (?, ?, ?)",
            (gym_id, "Main Branch", now),
        )
        return cursor.lastrowid
    return branch["id"]


def normalize_phone(phone: str) -> str:
    normalized = re.sub(r"\D", "", phone)
    if len(normalized) < 8:
        raise HTTPException(status_code=422, detail="Enter a valid phone number")
    return normalized


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "gym"


def unique_workspace_slug(connection: sqlite3.Connection, gym_name: str) -> str:
    base = slugify(gym_name)
    slug = base
    suffix = 2
    while connection.execute("SELECT 1 FROM gyms WHERE workspace_slug = ?", (slug,)).fetchone():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (TypeError, ValueError):
        return False


def branch_payload(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"]}


def user_payload(connection: sqlite3.Connection, user: sqlite3.Row, active_branch_id: int | None = None) -> dict:
    branches = connection.execute(
        """
        SELECT branches.id, branches.name
        FROM branches
        JOIN user_branch_access ON user_branch_access.branch_id = branches.id
        WHERE user_branch_access.user_id = ?
        ORDER BY branches.name
        """,
        (user["id"],),
    ).fetchall()
    return {
        "id": user["id"],
        "name": user["name"],
        "phone": user["phone"],
        "role": user["role"],
        "gym_id": user["gym_id"],
        "must_change_password": bool(user["must_change_password"]),
        "active_branch_id": active_branch_id,
        "branches": [branch_payload(branch) for branch in branches],
    }


def create_session(connection: sqlite3.Connection, user_id: int, active_branch_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    connection.execute(
        "INSERT INTO sessions (token, user_id, active_branch_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        (token, user_id, active_branch_id, now.isoformat(), (now + timedelta(days=30)).isoformat()),
    )
    return token


def get_current_session(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.removeprefix("Bearer ").strip()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT sessions.token, sessions.active_branch_id, sessions.expires_at,
                   users.id AS user_id, users.gym_id, users.name, users.phone,
                   users.role, users.is_active, users.must_change_password
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
        if row is None or not row["is_active"] or datetime.fromisoformat(row["expires_at"]) <= utc_now():
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        access = connection.execute(
            "SELECT 1 FROM user_branch_access WHERE user_id = ? AND branch_id = ?",
            (row["user_id"], row["active_branch_id"]),
        ).fetchone()
        if access is None:
            raise HTTPException(status_code=403, detail="Branch access denied")
        return dict(row)


def require_roles(*roles: UserRole):
    def check(session: Annotated[dict, Depends(get_current_session)]) -> dict:
        if session["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return session

    return check


def init_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS gyms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                workspace_slug TEXT NOT NULL UNIQUE,
                multi_branch_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gym_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(gym_id, name),
                FOREIGN KEY (gym_id) REFERENCES gyms(id)
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gym_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(gym_id, phone),
                FOREIGN KEY (gym_id) REFERENCES gyms(id)
            );
            CREATE TABLE IF NOT EXISTS user_branch_access (
                user_id INTEGER NOT NULL,
                branch_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, branch_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                active_branch_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (active_branch_id) REFERENCES branches(id)
            );
            CREATE TABLE IF NOT EXISTS whatsapp_connections (
                gym_id INTEGER PRIMARY KEY,
                business_account_id TEXT NOT NULL,
                phone_number_id TEXT NOT NULL,
                display_phone_number TEXT NOT NULL,
                renewal_template_name TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (gym_id) REFERENCES gyms(id)
            );
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id INTEGER,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                package TEXT NOT NULL,
                expires_on TEXT NOT NULL,
                joined_on TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (member_id) REFERENCES members(id)
            );
            CREATE TABLE IF NOT EXISTS plans (
                member_id INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                generated_on TEXT NOT NULL,
                FOREIGN KEY (member_id) REFERENCES members(id)
            );
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                weight_kg REAL NOT NULL,
                recorded_on TEXT NOT NULL,
                FOREIGN KEY (member_id) REFERENCES members(id)
            );
            """
        )
        ensure_column(connection, "members", "branch_id", "INTEGER")
        default_branch_id = ensure_demo_workspace(connection)
        connection.execute("UPDATE members SET branch_id = ? WHERE branch_id IS NULL", (default_branch_id,))
        count = connection.execute("SELECT COUNT(*) AS count FROM members").fetchone()["count"]
        if count:
            return
        today = date.today()
        members = [
            ("Aarav Sharma", "+91 98765 42010", "aarav@example.com", "Strength Annual", today + timedelta(days=2), today - timedelta(days=188)),
            ("Maya Patel", "+91 98765 42011", "maya@example.com", "Transform 3 Month", today + timedelta(days=5), today - timedelta(days=85)),
            ("Rohan Mehta", "+91 98765 42012", "rohan@example.com", "Open Gym Monthly", today + timedelta(days=18), today - timedelta(days=72)),
            ("Isha Verma", "+91 98765 42013", "isha@example.com", "Strength Annual", today + timedelta(days=94), today - timedelta(days=260)),
            ("Kabir Singh", "+91 98765 42014", "kabir@example.com", "Transform 3 Month", today + timedelta(days=7), today - timedelta(days=80)),
            ("Diya Kapoor", "+91 98765 42015", "diya@example.com", "Open Gym Monthly", today - timedelta(days=3), today - timedelta(days=35)),
        ]
        connection.executemany(
            "INSERT INTO members (branch_id, name, phone, email, package, expires_on, joined_on) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(default_branch_id, name, phone, email, package, expiry.isoformat(), joined.isoformat()) for name, phone, email, package, expiry, joined in members],
        )
        connection.executemany(
            "INSERT INTO progress (member_id, weight_kg, recorded_on) VALUES (?, ?, ?)",
            [
                (1, 82.4, (today - timedelta(days=92)).isoformat()),
                (1, 80.6, (today - timedelta(days=62)).isoformat()),
                (1, 78.9, (today - timedelta(days=31)).isoformat()),
                (1, 77.8, today.isoformat()),
            ],
        )
        connection.execute(
            "INSERT INTO plans (member_id, payload, generated_on) VALUES (?, ?, ?)",
            (1, json.dumps(build_plan(77.8, 178, 28, "get-lean")), today.isoformat()),
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="Forge Gym Platform API",
    description="MVP API for owner retention and member progression workflows.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/signup", status_code=201)
def signup(request: GymSignup) -> dict:
    branch_names = list(dict.fromkeys(name.strip() for name in request.branches if name.strip()))
    if not branch_names:
        raise HTTPException(status_code=422, detail="Add at least one branch")
    with get_connection() as connection:
        now = utc_now().isoformat()
        workspace_slug = unique_workspace_slug(connection, request.gym_name)
        gym_cursor = connection.execute(
            "INSERT INTO gyms (name, workspace_slug, multi_branch_enabled, created_at) VALUES (?, ?, ?, ?)",
            (request.gym_name.strip(), workspace_slug, int(len(branch_names) > 1), now),
        )
        gym_id = gym_cursor.lastrowid
        branch_ids = []
        for branch_name in branch_names:
            cursor = connection.execute(
                "INSERT INTO branches (gym_id, name, created_at) VALUES (?, ?, ?)",
                (gym_id, branch_name, now),
            )
            branch_ids.append(cursor.lastrowid)
        user_cursor = connection.execute(
            """
            INSERT INTO users (gym_id, name, phone, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (gym_id, request.owner_name.strip(), normalize_phone(request.phone), hash_password(request.password), "gym_owner", now),
        )
        user_id = user_cursor.lastrowid
        connection.executemany(
            "INSERT INTO user_branch_access (user_id, branch_id) VALUES (?, ?)",
            [(user_id, branch_id) for branch_id in branch_ids],
        )
        token = create_session(connection, user_id, branch_ids[0])
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        gym = connection.execute("SELECT * FROM gyms WHERE id = ?", (gym_id,)).fetchone()
        return {
            "token": token,
            "gym": {
                "id": gym_id,
                "name": gym["name"],
                "workspace_slug": workspace_slug,
                "multi_branch_enabled": bool(gym["multi_branch_enabled"]),
            },
            "user": user_payload(connection, user, branch_ids[0]),
        }


@app.post("/api/auth/login")
def login(request: LoginRequest) -> dict:
    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT users.*
            FROM users
            JOIN gyms ON gyms.id = users.gym_id
            WHERE gyms.workspace_slug = ? AND users.phone = ?
            """,
            (request.workspace_slug.lower(), normalize_phone(request.phone)),
        ).fetchone()
        if user is None or not user["is_active"] or not verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid workspace, phone number, or password")
        branch = connection.execute(
            "SELECT branch_id FROM user_branch_access WHERE user_id = ? ORDER BY branch_id LIMIT 1",
            (user["id"],),
        ).fetchone()
        if branch is None:
            raise HTTPException(status_code=403, detail="No branch access assigned")
        token = create_session(connection, user["id"], branch["branch_id"])
        return {"token": token, "user": user_payload(connection, user, branch["branch_id"])}


@app.get("/api/auth/me")
def current_user(session: Annotated[dict, Depends(get_current_session)]) -> dict:
    with get_connection() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        gym = connection.execute("SELECT * FROM gyms WHERE id = ?", (session["gym_id"],)).fetchone()
        return {
            "gym": {
                "id": gym["id"],
                "name": gym["name"],
                "workspace_slug": gym["workspace_slug"],
                "multi_branch_enabled": bool(gym["multi_branch_enabled"]),
            },
            "user": user_payload(connection, user, session["active_branch_id"]),
        }


@app.post("/api/auth/select-branch")
def select_branch(request: BranchSelection, session: Annotated[dict, Depends(get_current_session)]) -> dict:
    with get_connection() as connection:
        branch = connection.execute(
            """
            SELECT branches.id, branches.name
            FROM branches
            JOIN user_branch_access ON user_branch_access.branch_id = branches.id
            WHERE user_branch_access.user_id = ? AND branches.id = ?
            """,
            (session["user_id"], request.branch_id),
        ).fetchone()
        if branch is None:
            raise HTTPException(status_code=403, detail="Branch access denied")
        connection.execute(
            "UPDATE sessions SET active_branch_id = ? WHERE token = ?",
            (request.branch_id, session["token"]),
        )
        return {"active_branch": branch_payload(branch)}


@app.post("/api/auth/change-password")
def change_password(request: PasswordChange, session: Annotated[dict, Depends(get_current_session)]) -> dict:
    with get_connection() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if not verify_password(request.current_password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        connection.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (hash_password(request.new_password), session["user_id"]),
        )
    return {"status": "password-updated"}


@app.post("/api/auth/logout")
def logout(session: Annotated[dict, Depends(get_current_session)]) -> dict:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE token = ?", (session["token"],))
    return {"status": "logged-out"}


@app.get("/api/dashboard/summary")
def dashboard_summary(session: Annotated[dict, Depends(require_roles("gym_owner", "staff", "trainer"))]) -> dict:
    with get_connection() as connection:
        branch = connection.execute(
            "SELECT id, name FROM branches WHERE id = ? AND gym_id = ?",
            (session["active_branch_id"], session["gym_id"]),
        ).fetchone()
        member_rows = connection.execute(
            "SELECT expires_on FROM members WHERE branch_id = ?",
            (session["active_branch_id"],),
        ).fetchall()
    today = date.today()
    days_left = [(date.fromisoformat(member["expires_on"]) - today).days for member in member_rows]
    return {
        "branch": branch_payload(branch),
        "members": {
            "total": len(days_left),
            "active": sum(days >= 0 for days in days_left),
            "expiring_this_week": sum(0 <= days <= 7 for days in days_left),
            "expired": sum(days < 0 for days in days_left),
        },
    }


@app.get("/api/access/users")
def list_workspace_users(session: Annotated[dict, Depends(require_roles("gym_owner"))]) -> list[dict]:
    with get_connection() as connection:
        users = connection.execute(
            "SELECT * FROM users WHERE gym_id = ? ORDER BY role, name",
            (session["gym_id"],),
        ).fetchall()
        return [user_payload(connection, user) for user in users]


@app.post("/api/access/users", status_code=201)
def provision_user(request: UserProvision, session: Annotated[dict, Depends(require_roles("gym_owner"))]) -> dict:
    branch_ids = list(dict.fromkeys(request.branch_ids))
    with get_connection() as connection:
        branches = connection.execute(
            f"SELECT id FROM branches WHERE gym_id = ? AND id IN ({','.join('?' for _ in branch_ids)})",
            (session["gym_id"], *branch_ids),
        ).fetchall()
        if len(branches) != len(branch_ids):
            raise HTTPException(status_code=422, detail="Every branch must belong to your gym")
        try:
            cursor = connection.execute(
                """
                INSERT INTO users (gym_id, name, phone, password_hash, role, must_change_password, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["gym_id"],
                    request.name.strip(),
                    normalize_phone(request.phone),
                    hash_password(request.temporary_password),
                    request.role,
                    1,
                    utc_now().isoformat(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="This phone number already has access to the gym") from error
        connection.executemany(
            "INSERT INTO user_branch_access (user_id, branch_id) VALUES (?, ?)",
            [(cursor.lastrowid, branch_id) for branch_id in branch_ids],
        )
        user = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return user_payload(connection, user)


def whatsapp_connection_payload(row: sqlite3.Row | None) -> dict:
    if row is None:
        return {
            "connected": False,
            "status": "not-configured",
            "business_account_id": None,
            "phone_number_id": None,
            "display_phone_number": None,
            "renewal_template_name": None,
        }
    return {
        "connected": row["status"] == "connected",
        "status": row["status"],
        "business_account_id": row["business_account_id"],
        "phone_number_id": row["phone_number_id"],
        "display_phone_number": row["display_phone_number"],
        "renewal_template_name": row["renewal_template_name"],
    }


@app.get("/api/integrations/whatsapp")
def get_whatsapp_connection(session: Annotated[dict, Depends(require_roles("gym_owner"))]) -> dict:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM whatsapp_connections WHERE gym_id = ?",
            (session["gym_id"],),
        ).fetchone()
    return whatsapp_connection_payload(row)


@app.put("/api/integrations/whatsapp")
def configure_whatsapp_connection(
    request: WhatsAppConnectionUpdate,
    session: Annotated[dict, Depends(require_roles("gym_owner"))],
) -> dict:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO whatsapp_connections (
                gym_id, business_account_id, phone_number_id, display_phone_number,
                renewal_template_name, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(gym_id) DO UPDATE SET
                business_account_id = excluded.business_account_id,
                phone_number_id = excluded.phone_number_id,
                display_phone_number = excluded.display_phone_number,
                renewal_template_name = excluded.renewal_template_name,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                session["gym_id"],
                request.business_account_id.strip(),
                request.phone_number_id.strip(),
                request.display_phone_number.strip(),
                request.renewal_template_name.strip(),
                "pending-verification",
                utc_now().isoformat(),
            ),
        )
        row = connection.execute(
            "SELECT * FROM whatsapp_connections WHERE gym_id = ?",
            (session["gym_id"],),
        ).fetchone()
    return whatsapp_connection_payload(row)


def row_to_member(row: sqlite3.Row) -> dict:
    today = date.today()
    expires_on = date.fromisoformat(row["expires_on"])
    days_left = (expires_on - today).days
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "email": row["email"],
        "package": row["package"],
        "expires_on": row["expires_on"],
        "joined_on": row["joined_on"],
        "days_left": days_left,
        "status": "expired" if days_left < 0 else "expiring" if days_left <= 7 else "active",
    }


def build_plan(weight_kg: float, height_cm: float, age: int, goal: Goal) -> dict:
    goal_config = {
        "lose-weight": {"label": "Lose weight", "calorie_factor": 24, "protein": 1.7, "focus": "steady fat loss"},
        "build-muscle": {"label": "Build muscle", "calorie_factor": 34, "protein": 2.0, "focus": "progressive strength"},
        "get-lean": {"label": "Get lean", "calorie_factor": 28, "protein": 1.9, "focus": "body recomposition"},
    }[goal]
    calories = round(weight_kg * goal_config["calorie_factor"] / 50) * 50
    protein = round(weight_kg * goal_config["protein"])
    bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)
    meals = [
        {"time": "07:30", "name": "Protein-first breakfast", "detail": "Eggs or paneer, oats, seasonal fruit", "calories": round(calories * 0.24)},
        {"time": "12:45", "name": "Balanced lunch", "detail": "Lean protein, rice or roti, vegetables, curd", "calories": round(calories * 0.34)},
        {"time": "16:30", "name": "Training snack", "detail": "Fruit, yogurt, and a small handful of nuts", "calories": round(calories * 0.14)},
        {"time": "20:00", "name": "Recovery dinner", "detail": "Protein, cooked vegetables, and a lighter carb portion", "calories": round(calories * 0.28)},
    ]
    workouts = [
        {"week": 1, "theme": "Build the base", "sessions": ["Full body strength", "Zone 2 cardio + mobility", "Upper body + core", "Lower body technique"], "target": "Move with control and finish fresh."},
        {"week": 2, "theme": "Add volume", "sessions": ["Lower body strength", "Upper body strength", "Intervals + core", "Full body circuit"], "target": "Add one working set to main lifts."},
        {"week": 3, "theme": "Progressive push", "sessions": ["Lower body progressive", "Upper body progressive", "Conditioning intervals", "Full body strength"], "target": "Increase load slightly while keeping form."},
        {"week": 4, "theme": "Consolidate", "sessions": ["Full body strength", "Cardio + mobility", "Upper and core", "Lower and conditioning"], "target": "Repeat your strongest week with clean reps."},
    ]
    return {
        "goal": goal,
        "goal_label": goal_config["label"],
        "focus": goal_config["focus"],
        "daily_calories": calories,
        "daily_protein_g": protein,
        "water_liters": round(max(2.2, weight_kg * 0.035), 1),
        "bmi": bmi,
        "age": age,
        "meals": meals,
        "workouts": workouts,
        "note": "This starter plan is general fitness guidance. Adjust with a qualified coach for injuries or medical needs.",
    }


def require_member(connection: sqlite3.Connection, member_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return row


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/members")
def list_members() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM members ORDER BY expires_on ASC").fetchall()
    return [row_to_member(row) for row in rows]


@app.post("/api/members", status_code=201)
def create_member(member: MemberCreate) -> dict:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO members (name, phone, email, package, expires_on, joined_on) VALUES (?, ?, ?, ?, ?, ?)",
            (member.name, member.phone, member.email, member.package, member.expires_on.isoformat(), date.today().isoformat()),
        )
        row = connection.execute("SELECT * FROM members WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return row_to_member(row)


@app.get("/api/members/expiring")
def list_expiring_members() -> list[dict]:
    today = date.today().isoformat()
    through = (date.today() + timedelta(days=7)).isoformat()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM members WHERE expires_on BETWEEN ? AND ? ORDER BY expires_on ASC",
            (today, through),
        ).fetchall()
    return [row_to_member(row) for row in rows]


@app.post("/api/reminders/expiring")
def send_expiring_reminders() -> dict:
    members = list_expiring_members()
    for member in members:
        send_reminder(member["id"])
    return {"queued": len(members), "channel": "whatsapp", "status": "queued-demo"}


@app.post("/api/reminders/{member_id}")
def send_reminder(member_id: int) -> dict:
    with get_connection() as connection:
        member = require_member(connection, member_id)
        sent_at = date.today().isoformat()
        connection.execute(
            "INSERT INTO reminders (member_id, sent_at, channel, status) VALUES (?, ?, ?, ?)",
            (member_id, sent_at, "whatsapp", "queued-demo"),
        )
    return {
        "member_id": member_id,
        "member_name": member["name"],
        "channel": "whatsapp",
        "status": "queued-demo",
        "message": f"Renewal reminder queued for {member['name']}.",
    }


@app.post("/api/plans/generate")
def generate_plan(request: PlanRequest) -> dict:
    with get_connection() as connection:
        require_member(connection, request.member_id)
        plan = build_plan(request.weight_kg, request.height_cm, request.age, request.goal)
        connection.execute(
            """
            INSERT INTO plans (member_id, payload, generated_on) VALUES (?, ?, ?)
            ON CONFLICT(member_id) DO UPDATE SET payload = excluded.payload, generated_on = excluded.generated_on
            """,
            (request.member_id, json.dumps(plan), date.today().isoformat()),
        )
    return plan


@app.get("/api/plans/{member_id}")
def get_plan(member_id: int) -> dict:
    with get_connection() as connection:
        require_member(connection, member_id)
        row = connection.execute("SELECT payload FROM plans WHERE member_id = ?", (member_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Plan not generated yet")
    return json.loads(row["payload"])


@app.get("/api/progress/{member_id}")
def list_progress(member_id: int) -> list[dict]:
    with get_connection() as connection:
        require_member(connection, member_id)
        rows = connection.execute(
            "SELECT id, weight_kg, recorded_on FROM progress WHERE member_id = ? ORDER BY recorded_on ASC",
            (member_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/progress/{member_id}", status_code=201)
def add_progress(member_id: int, entry: ProgressCreate) -> dict:
    with get_connection() as connection:
        require_member(connection, member_id)
        cursor = connection.execute(
            "INSERT INTO progress (member_id, weight_kg, recorded_on) VALUES (?, ?, ?)",
            (member_id, entry.weight_kg, entry.recorded_on.isoformat()),
        )
    return {"id": cursor.lastrowid, "member_id": member_id, "weight_kg": entry.weight_kg, "recorded_on": entry.recorded_on.isoformat()}
