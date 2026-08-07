"""Backward-compatible export — prefer interface.api."""

from app.modules.identity.interface.api import router

__all__ = ["router"]
