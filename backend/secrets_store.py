from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")
APP_ENV = os.getenv("GYM_APP_ENV", "development").lower()
configured_key = os.getenv("GYM_SECRET_ENCRYPTION_KEY")
if not configured_key and APP_ENV == "production":
    raise RuntimeError("GYM_SECRET_ENCRYPTION_KEY is required in production")
if not configured_key:
    configured_key = base64.urlsafe_b64encode(hashlib.sha256(b"forge-local-development-key").digest()).decode()

fernet = Fernet(configured_key.encode())


def encrypt_secret(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return fernet.decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise RuntimeError("Stored integration secret cannot be decrypted") from error
