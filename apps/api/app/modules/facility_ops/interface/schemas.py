from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WorkOrderCreate(BaseModel):
    park_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = "GENERAL"
    priority: str = "MEDIUM"
    assignee_user_id: Optional[int] = None
    unit_id: Optional[int] = None
    due_at: Optional[str] = None
