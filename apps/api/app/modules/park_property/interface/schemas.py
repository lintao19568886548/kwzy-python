from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ParkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    address: str = ""
    area: float = 0
    contact: Optional[str] = None
    manager: Optional[str] = None
    description: Optional[str] = None
    status: str = "ACTIVE"


class ParkUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    area: Optional[float] = None
    contact: Optional[str] = None
    manager: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class UnitCreate(BaseModel):
    park_id: int
    building_id: Optional[int] = None
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    rentable_area: float = 0
    base_rent_price: float = 0
    status: str = "VACANT"
    attributes: Optional[dict[str, Any]] = None


class UnitUpdate(BaseModel):
    name: Optional[str] = None
    rentable_area: Optional[float] = None
    base_rent_price: Optional[float] = None
    status: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class UnitStatusUpdate(BaseModel):
    status: str
