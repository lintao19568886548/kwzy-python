"""Backward-compatible export — prefer interface.api."""

from app.modules.park_property.interface.api import router

__all__ = ["router"]
