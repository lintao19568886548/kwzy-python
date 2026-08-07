"""Backward-compatible re-export — prefer infrastructure.database.session."""

from app.infrastructure.database.session import SessionLocal, engine, get_db

__all__ = ["SessionLocal", "engine", "get_db"]
