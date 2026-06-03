from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATABASE_PATH = Path(os.getenv("GYM_DATABASE_PATH", BASE_DIR / "gym_platform.db"))
DATABASE_URL = os.getenv("GYM_DATABASE_URL", f"sqlite:///{DATABASE_PATH.as_posix()}")
IS_SQLITE = DATABASE_URL.startswith("sqlite")
APP_ENV = os.getenv("GYM_APP_ENV", "development").lower()
if APP_ENV == "production" and IS_SQLITE:
    raise RuntimeError("GYM_DATABASE_URL must point to PostgreSQL in production")


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=True,
)


if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
