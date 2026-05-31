from __future__ import annotations

import json
import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("GYM_DATABASE_PATH", BASE_DIR / "gym_platform.db"))

Goal = Literal["lose-weight", "build-muscle", "get-lean"]


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


def init_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            "INSERT INTO members (name, phone, email, package, expires_on, joined_on) VALUES (?, ?, ?, ?, ?, ?)",
            [(name, phone, email, package, expiry.isoformat(), joined.isoformat()) for name, phone, email, package, expiry, joined in members],
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
