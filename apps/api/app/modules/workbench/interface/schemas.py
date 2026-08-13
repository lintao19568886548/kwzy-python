"""功能说明：WorkItem 请求体。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WorkItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    park_id: Optional[int] = None
    item_type: str = "MANUAL"
    priority: str = "MEDIUM"
    assignee_user_id: Optional[int] = None
    due_at: Optional[str] = None
    sort_order: int = 0
