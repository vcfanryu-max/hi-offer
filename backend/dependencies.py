from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.security import ApiKeyStore


api_key_store = ApiKeyStore()


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_key_store() -> ApiKeyStore:
    return api_key_store

