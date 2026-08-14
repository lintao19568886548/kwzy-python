"""功能说明：WorkItem 仓储（租户 + 园区 scope）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.workbench import WorkItem
from app.shared.tenant_context import ParkScopeMode, TenantContext


class WorkItemRepository:
    """功能说明：待办/工作项持久化，强制 tenant 与 park 可见性。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _scope(self, stmt):
        """ALL：租户内全部；LIST：本园 + 无园区级；NONE：仅指派给自己。"""

        stmt = stmt.where(WorkItem.tenant_id == self.ctx.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(
                or_(
                    WorkItem.park_id.is_(None),
                    WorkItem.park_id.in_(list(self.ctx.park_ids)),
                )
            )
        # NONE：仅个人指派
        if self.ctx.user_id:
            return stmt.where(WorkItem.assignee_user_id == int(self.ctx.user_id))
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        assignee_user_id: Optional[int] = None,
        item_type: Optional[str] = None,
        mine: bool = False,
    ) -> Sequence[WorkItem]:
        stmt = self._scope(select(WorkItem))
        if status:
            stmt = stmt.where(WorkItem.status == status)
        if park_id is not None:
            stmt = stmt.where(WorkItem.park_id == int(park_id))
        if assignee_user_id is not None:
            stmt = stmt.where(WorkItem.assignee_user_id == int(assignee_user_id))
        if item_type:
            stmt = stmt.where(WorkItem.item_type == item_type)
        if mine and self.ctx.user_id:
            stmt = stmt.where(WorkItem.assignee_user_id == int(self.ctx.user_id))
        return list(
            self.session.scalars(
                stmt.order_by(WorkItem.sort_order.asc(), WorkItem.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def count(
        self,
        *,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        assignee_user_id: Optional[int] = None,
        item_type: Optional[str] = None,
        mine: bool = False,
    ) -> int:
        vis = self._scope(select(WorkItem.id))
        if status:
            vis = vis.where(WorkItem.status == status)
        if park_id is not None:
            vis = vis.where(WorkItem.park_id == int(park_id))
        if assignee_user_id is not None:
            vis = vis.where(WorkItem.assignee_user_id == int(assignee_user_id))
        if item_type:
            vis = vis.where(WorkItem.item_type == item_type)
        if mine and self.ctx.user_id:
            vis = vis.where(WorkItem.assignee_user_id == int(self.ctx.user_id))
        return int(self.session.scalar(select(func.count()).select_from(vis.subquery())) or 0)

    def get_by_id(self, work_item_id: int, *, for_update: bool = False) -> Optional[WorkItem]:
        stmt = self._scope(select(WorkItem).where(WorkItem.id == work_item_id))
        if for_update:
            dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
            if dialect == "postgresql":
                stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def get_by_source(
        self,
        *,
        source_type: str,
        source_id: str,
        item_type: str,
        for_update: bool = False,
    ) -> Optional[WorkItem]:
        """按业务来源键查找（租户内，忽略 park scope，供幂等 upsert）。"""

        stmt = select(WorkItem).where(
            WorkItem.tenant_id == self.ctx.tenant_id,
            WorkItem.source_type == source_type,
            WorkItem.source_id == source_id,
            WorkItem.item_type == item_type,
        )
        if for_update:
            dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
            if dialect == "postgresql":
                stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def add(self, model: WorkItem) -> WorkItem:
        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def create(
        self,
        *,
        park_id: Optional[int],
        item_type: str,
        title: str,
        description: Optional[str],
        status: str,
        priority: str,
        assignee_user_id: Optional[int],
        due_at,
        source_type: str,
        source_id: str,
        sort_order: int = 0,
        deep_link: Optional[str] = None,
        source_owned: bool = False,
        last_event_id: Optional[int] = None,
    ) -> WorkItem:
        model = WorkItem(
            park_id=park_id,
            item_type=item_type,
            title=title,
            description=description,
            status=status,
            priority=priority,
            assignee_user_id=assignee_user_id,
            due_at=due_at,
            source_type=source_type,
            source_id=source_id,
            sort_order=sort_order,
            deep_link=deep_link,
            source_owned=source_owned,
            last_event_id=last_event_id,
            lock_version=1,
        )
        return self.add(model)

    def list_with_total(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        assignee_user_id: Optional[int] = None,
        item_type: Optional[str] = None,
        mine: bool = False,
    ) -> tuple[int, Sequence[WorkItem]]:
        """Return a page and its total in one round trip for normal, non-empty pages."""

        stmt = self._scope(select(WorkItem, func.count().over().label("page_total")))
        if status:
            stmt = stmt.where(WorkItem.status == status)
        if park_id is not None:
            stmt = stmt.where(WorkItem.park_id == int(park_id))
        if assignee_user_id is not None:
            stmt = stmt.where(WorkItem.assignee_user_id == int(assignee_user_id))
        if item_type:
            stmt = stmt.where(WorkItem.item_type == item_type)
        if mine and self.ctx.user_id:
            stmt = stmt.where(WorkItem.assignee_user_id == int(self.ctx.user_id))
        result = self.session.execute(
            stmt.order_by(WorkItem.sort_order.asc(), WorkItem.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        if result:
            return int(result[0][1]), [row[0] for row in result]
        if offset:
            return (
                self.count(
                    status=status,
                    park_id=park_id,
                    assignee_user_id=assignee_user_id,
                    item_type=item_type,
                    mine=mine,
                ),
                [],
            )
        return 0, []

    def open_metrics(
        self,
        *,
        park_id: Optional[int],
        now: datetime,
        horizon: datetime,
    ) -> tuple[int, int, int]:
        """Aggregate open, overdue and due-soon counts without loading a bounded row sample."""

        stmt = self._scope(
            select(
                func.count(WorkItem.id),
                func.sum(case((WorkItem.due_at < now, 1), else_=0)),
                func.sum(
                    case(
                        (
                            WorkItem.due_at.is_not(None)
                            & (WorkItem.due_at >= now)
                            & (WorkItem.due_at <= horizon),
                            1,
                        ),
                        else_=0,
                    )
                ),
            )
        ).where(WorkItem.status == "OPEN")
        if park_id is not None:
            stmt = stmt.where(WorkItem.park_id == int(park_id))
        row = self.session.execute(stmt).one()
        return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)

    def save(self, model: WorkItem) -> WorkItem:
        if int(model.tenant_id) != self.ctx.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model
