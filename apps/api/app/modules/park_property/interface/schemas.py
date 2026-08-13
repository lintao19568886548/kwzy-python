from __future__ import annotations

from datetime import date
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
    rentable_area: float = Field(default=0, ge=0)
    base_rent_price: float = Field(default=0, ge=0)
    usage_type: str = "FACTORY"
    billing_unit: str = "SQM"
    available_from: Optional[date] = None
    status: str = "VACANT"
    attributes: Optional[dict[str, Any]] = None


class UnitUpdate(BaseModel):
    expected_lock_version: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = None
    rentable_area: Optional[float] = Field(default=None, ge=0)
    base_rent_price: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class UnitStatusUpdate(BaseModel):
    status: str


class SpatialCreate(BaseModel):
    park_id: int
    parent_id: Optional[int] = None
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    node_type: str
    building_type: str = "FACTORY"
    sort_order: int = 0
    status: str = "ACTIVE"
    address: str = ""
    description: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class SpatialUpdate(BaseModel):
    parent_id: Optional[int] = None
    code: Optional[str] = Field(default=None, min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    node_type: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class UnitVersionCreate(BaseModel):
    expected_lock_version: int = Field(ge=1)
    building_id: Optional[int] = None
    code: Optional[str] = Field(default=None, min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    rentable_area: Optional[float] = Field(default=None, gt=0)
    usage_type: Optional[str] = None
    billing_unit: Optional[str] = None
    available_from: Optional[date] = None
    base_rent_price: Optional[float] = Field(default=None, ge=0)
    attributes: Optional[dict[str, Any]] = None


class UnitSplitTarget(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    rentable_area: float = Field(gt=0)
    usage_type: Optional[str] = None
    base_rent_price: Optional[float] = Field(default=None, ge=0)


class UnitSplitRequest(BaseModel):
    unit_id: int
    expected_lock_version: int = Field(ge=1)
    targets: list[UnitSplitTarget] = Field(min_length=2)


class UnitMergeSource(BaseModel):
    unit_id: int
    expected_lock_version: int = Field(ge=1)


class UnitMergeRequest(BaseModel):
    sources: list[UnitMergeSource] = Field(min_length=2)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    usage_type: Optional[str] = None
    base_rent_price: Optional[float] = Field(default=None, ge=0)
