"""Tenant-safe persistence for event-driven workbench automation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.identity import Role, User, UserRole
from app.infrastructure.database.models.workbench_automation import (
    AutomationExecution,
    AutomationRule,
    AutomationRuleVersion,
    BusinessEvent,
    EventConsumerLog,
    InAppNotification,
    SchedulerDefinition,
    SchedulerRun,
    WorkbenchLayout,
    WorkbenchWidget,
)
from app.shared.tenant_context import ParkScopeMode, TenantContext


class AutomationRepository:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def _park_visible(self, column):
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return True
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return or_(column.is_(None), column.in_(list(self.ctx.park_ids)))
        return column.is_(None)

    def user_exists(self, user_id: int) -> bool:
        return (
            self.session.scalar(
                select(func.count()).select_from(User).where(
                    User.id == int(user_id),
                    User.tenant_id == self.ctx.tenant_id,
                    User.status == "ACTIVE",
                )
            )
            or 0
        ) > 0

    def role_exists(self, role_id: int) -> bool:
        return (
            self.session.scalar(
                select(func.count()).select_from(Role).where(
                    Role.id == int(role_id), Role.tenant_id == self.ctx.tenant_id
                )
            )
            or 0
        ) > 0

    def role_by_id(self, role_id: int) -> Optional[Role]:
        return self.session.scalars(
            select(Role).where(
                Role.id == int(role_id),
                Role.tenant_id == self.ctx.tenant_id,
                Role.status == "ACTIVE",
            )
        ).first()

    # Events and consumers -------------------------------------------------

    def event_by_key(self, idempotency_key: str) -> Optional[BusinessEvent]:
        return self.session.scalars(
            select(BusinessEvent).where(
                BusinessEvent.tenant_id == self.ctx.tenant_id,
                BusinessEvent.idempotency_key == idempotency_key,
            )
        ).first()

    def event_by_id(self, event_id: int) -> Optional[BusinessEvent]:
        return self.session.scalars(
            select(BusinessEvent).where(
                BusinessEvent.id == int(event_id),
                BusinessEvent.tenant_id == self.ctx.tenant_id,
                self._park_visible(BusinessEvent.park_id),
            )
        ).first()

    def create_event(
        self,
        *,
        park_id: Optional[int],
        event_type: str,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        schema_version: int,
        payload_json: str,
        occurred_at: datetime,
        consumers: Sequence[str],
        max_attempts: int,
    ) -> BusinessEvent:
        row = BusinessEvent(
            tenant_id=self.ctx.tenant_id,
            park_id=park_id,
            event_type=event_type,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            schema_version=schema_version,
            payload_json=payload_json,
            occurred_at=occurred_at,
        )
        self.session.add(row)
        self.session.flush()
        for consumer in consumers:
            self.session.add(
                EventConsumerLog(
                    tenant_id=self.ctx.tenant_id,
                    event_id=row.id,
                    consumer_name=consumer,
                    generation=1,
                    status="PENDING",
                    attempt_count=0,
                    max_attempts=max_attempts,
                )
            )
        self.session.flush()
        return row

    def list_events(
        self,
        *,
        offset: int,
        limit: int,
        event_type: Optional[str],
        park_id: Optional[int],
    ) -> tuple[int, Sequence[BusinessEvent]]:
        filters: list[Any] = [
            BusinessEvent.tenant_id == self.ctx.tenant_id,
            self._park_visible(BusinessEvent.park_id),
        ]
        if event_type:
            filters.append(BusinessEvent.event_type == event_type)
        if park_id is not None:
            filters.append(BusinessEvent.park_id == int(park_id))
        total = int(
            self.session.scalar(select(func.count()).select_from(BusinessEvent).where(*filters)) or 0
        )
        rows = self.session.scalars(
            select(BusinessEvent)
            .where(*filters)
            .order_by(BusinessEvent.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return total, list(rows)

    def consumers_for_event(self, event_id: int) -> Sequence[EventConsumerLog]:
        return list(
            self.session.scalars(
                select(EventConsumerLog)
                .where(
                    EventConsumerLog.tenant_id == self.ctx.tenant_id,
                    EventConsumerLog.event_id == int(event_id),
                )
                .order_by(EventConsumerLog.consumer_name, EventConsumerLog.generation)
            ).all()
        )

    def consumers_for_events(self, event_ids: Sequence[int]) -> dict[int, list[EventConsumerLog]]:
        ids = [int(value) for value in event_ids]
        if not ids:
            return {}
        grouped: dict[int, list[EventConsumerLog]] = {event_id: [] for event_id in ids}
        rows = self.session.scalars(
            select(EventConsumerLog)
            .where(
                EventConsumerLog.tenant_id == self.ctx.tenant_id,
                EventConsumerLog.event_id.in_(ids),
            )
            .order_by(EventConsumerLog.event_id, EventConsumerLog.generation)
        ).all()
        for row in rows:
            grouped.setdefault(int(row.event_id), []).append(row)
        return grouped

    def claim_consumers(
        self, *, consumer_name: str, worker_id: str, limit: int, now: datetime
    ) -> Sequence[EventConsumerLog]:
        stmt = (
            select(EventConsumerLog)
            .join(BusinessEvent, BusinessEvent.id == EventConsumerLog.event_id)
            .where(
                EventConsumerLog.tenant_id == self.ctx.tenant_id,
                EventConsumerLog.consumer_name == consumer_name,
                EventConsumerLog.status.in_(("PENDING", "RETRY")),
                or_(
                    EventConsumerLog.next_attempt_at.is_(None),
                    EventConsumerLog.next_attempt_at <= now,
                ),
                self._park_visible(BusinessEvent.park_id),
            )
            .order_by(EventConsumerLog.id)
            .limit(limit)
        )
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True, of=EventConsumerLog)
        rows = list(self.session.scalars(stmt).all())
        for row in rows:
            row.status = "RUNNING"
            row.claimed_by = worker_id
            row.claimed_at = now
            row.attempt_count = int(row.attempt_count) + 1
            self.session.add(row)
        self.session.flush()
        return rows

    def consumer_by_id(self, consumer_id: int, *, for_update: bool = False) -> Optional[EventConsumerLog]:
        stmt = (
            select(EventConsumerLog)
            .join(BusinessEvent, BusinessEvent.id == EventConsumerLog.event_id)
            .where(
                EventConsumerLog.id == int(consumer_id),
                EventConsumerLog.tenant_id == self.ctx.tenant_id,
                self._park_visible(BusinessEvent.park_id),
            )
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(of=EventConsumerLog)
        return self.session.scalars(stmt).first()

    def next_consumer_generation(self, row: EventConsumerLog) -> int:
        return int(
            self.session.scalar(
                select(func.max(EventConsumerLog.generation)).where(
                    EventConsumerLog.tenant_id == self.ctx.tenant_id,
                    EventConsumerLog.event_id == row.event_id,
                    EventConsumerLog.consumer_name == row.consumer_name,
                )
            )
            or 0
        ) + 1

    def add_consumer_generation(self, row: EventConsumerLog, generation: int) -> EventConsumerLog:
        new_row = EventConsumerLog(
            tenant_id=self.ctx.tenant_id,
            event_id=row.event_id,
            consumer_name=row.consumer_name,
            generation=generation,
            status="PENDING",
            attempt_count=0,
            max_attempts=row.max_attempts,
        )
        self.session.add(new_row)
        self.session.flush()
        return new_row

    # Rules and execution --------------------------------------------------

    def rule_by_id(self, rule_id: int, *, for_update: bool = False) -> Optional[AutomationRule]:
        stmt = select(AutomationRule).where(
            AutomationRule.id == int(rule_id),
            AutomationRule.tenant_id == self.ctx.tenant_id,
            self._park_visible(AutomationRule.park_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def rule_by_code(self, code: str) -> Optional[AutomationRule]:
        return self.session.scalars(
            select(AutomationRule).where(
                AutomationRule.tenant_id == self.ctx.tenant_id, AutomationRule.code == code
            )
        ).first()

    def list_rules(self) -> Sequence[AutomationRule]:
        return list(
            self.session.scalars(
                select(AutomationRule)
                .where(
                    AutomationRule.tenant_id == self.ctx.tenant_id,
                    self._park_visible(AutomationRule.park_id),
                )
                .order_by(AutomationRule.code)
            ).all()
        )

    def create_rule(self, **values: Any) -> AutomationRule:
        row = AutomationRule(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def version_by_id(self, version_id: int) -> Optional[AutomationRuleVersion]:
        return self.session.scalars(
            select(AutomationRuleVersion).where(
                AutomationRuleVersion.id == int(version_id),
                AutomationRuleVersion.tenant_id == self.ctx.tenant_id,
            )
        ).first()

    def rule_versions(self, rule_id: int) -> Sequence[AutomationRuleVersion]:
        return list(
            self.session.scalars(
                select(AutomationRuleVersion)
                .where(
                    AutomationRuleVersion.tenant_id == self.ctx.tenant_id,
                    AutomationRuleVersion.rule_id == int(rule_id),
                )
                .order_by(AutomationRuleVersion.version.desc())
            ).all()
        )

    def draft_for_rule(self, rule_id: int) -> Optional[AutomationRuleVersion]:
        return self.session.scalars(
            select(AutomationRuleVersion).where(
                AutomationRuleVersion.tenant_id == self.ctx.tenant_id,
                AutomationRuleVersion.rule_id == int(rule_id),
                AutomationRuleVersion.status == "DRAFT",
            )
        ).first()

    def add_rule_version(self, **values: Any) -> AutomationRuleVersion:
        row = AutomationRuleVersion(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def matching_versions(
        self, *, event_type: str, park_id: Optional[int]
    ) -> Sequence[AutomationRuleVersion]:
        stmt = (
            select(AutomationRuleVersion)
            .join(AutomationRule, AutomationRule.id == AutomationRuleVersion.rule_id)
            .where(
                AutomationRuleVersion.tenant_id == self.ctx.tenant_id,
                AutomationRuleVersion.event_type == event_type,
                AutomationRuleVersion.status == "PUBLISHED",
                AutomationRule.status == "ACTIVE",
                or_(AutomationRule.park_id.is_(None), AutomationRule.park_id == park_id),
            )
            .order_by(AutomationRuleVersion.priority, AutomationRuleVersion.id)
        )
        return list(self.session.scalars(stmt).all())

    def execution_for(
        self, *, event_id: int, version_id: int
    ) -> Optional[AutomationExecution]:
        return self.session.scalars(
            select(AutomationExecution).where(
                AutomationExecution.tenant_id == self.ctx.tenant_id,
                AutomationExecution.event_id == int(event_id),
                AutomationExecution.rule_version_id == int(version_id),
            )
        ).first()

    def add_execution(self, **values: Any) -> AutomationExecution:
        row = AutomationExecution(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def list_executions(self, *, limit: int = 100) -> Sequence[AutomationExecution]:
        return list(
            self.session.scalars(
                select(AutomationExecution)
                .where(AutomationExecution.tenant_id == self.ctx.tenant_id)
                .order_by(AutomationExecution.id.desc())
                .limit(limit)
            ).all()
        )

    # Notifications --------------------------------------------------------

    def notification_by_key(self, idempotency_key: str) -> Optional[InAppNotification]:
        return self.session.scalars(
            select(InAppNotification).where(
                InAppNotification.tenant_id == self.ctx.tenant_id,
                InAppNotification.idempotency_key == idempotency_key,
            )
        ).first()

    def add_notification(self, **values: Any) -> InAppNotification:
        row = InAppNotification(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def _notification_scope(self):
        return (
            InAppNotification.tenant_id == self.ctx.tenant_id,
            InAppNotification.recipient_user_id == int(self.ctx.user_id or 0),
            self._park_visible(InAppNotification.park_id),
        )

    def list_notifications(
        self, *, offset: int, limit: int, status: Optional[str]
    ) -> tuple[int, int, Sequence[InAppNotification]]:
        filters: list[Any] = list(self._notification_scope())
        if status:
            filters.append(InAppNotification.status == status)
        total_sq = (
            select(func.count())
            .select_from(InAppNotification)
            .where(*filters)
            .correlate(None)
            .scalar_subquery()
        )
        unread_sq = (
            select(func.count())
            .select_from(InAppNotification)
            .where(*self._notification_scope(), InAppNotification.status == "UNREAD")
            .correlate(None)
            .scalar_subquery()
        )
        result = self.session.execute(
            select(
                InAppNotification,
                total_sq.label("notification_total"),
                unread_sq.label("notification_unread"),
            )
            .where(*filters)
            .order_by(InAppNotification.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        if result:
            return int(result[0][1]), int(result[0][2]), [row[0] for row in result]
        counts = self.session.execute(select(total_sq, unread_sq)).one()
        return int(counts[0] or 0), int(counts[1] or 0), []

    def unread_count(self) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(InAppNotification).where(
                    *self._notification_scope(), InAppNotification.status == "UNREAD"
                )
            )
            or 0
        )

    def notification_by_id(
        self, notification_id: int, *, for_update: bool = False
    ) -> Optional[InAppNotification]:
        stmt = select(InAppNotification).where(
            InAppNotification.id == int(notification_id), *self._notification_scope()
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def notifications_by_ids(self, ids: Sequence[int], *, for_update: bool) -> Sequence[InAppNotification]:
        stmt = select(InAppNotification).where(
            InAppNotification.id.in_([int(value) for value in ids]), *self._notification_scope()
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return list(self.session.scalars(stmt).all())

    # Scheduler ------------------------------------------------------------

    def schedule_by_id(
        self, schedule_id: int, *, for_update: bool = False
    ) -> Optional[SchedulerDefinition]:
        stmt = select(SchedulerDefinition).where(
            SchedulerDefinition.id == int(schedule_id),
            SchedulerDefinition.tenant_id == self.ctx.tenant_id,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def schedule_by_code(self, code: str) -> Optional[SchedulerDefinition]:
        return self.session.scalars(
            select(SchedulerDefinition).where(
                SchedulerDefinition.tenant_id == self.ctx.tenant_id,
                SchedulerDefinition.code == code,
            )
        ).first()

    def add_schedule(self, **values: Any) -> SchedulerDefinition:
        row = SchedulerDefinition(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def list_schedules(self) -> Sequence[SchedulerDefinition]:
        return list(
            self.session.scalars(
                select(SchedulerDefinition)
                .where(SchedulerDefinition.tenant_id == self.ctx.tenant_id)
                .order_by(SchedulerDefinition.code)
            ).all()
        )

    def due_schedules(self, *, now: datetime, limit: int) -> Sequence[SchedulerDefinition]:
        stmt = (
            select(SchedulerDefinition)
            .where(
                SchedulerDefinition.tenant_id == self.ctx.tenant_id,
                SchedulerDefinition.enabled.is_(True),
                SchedulerDefinition.next_run_at.is_not(None),
                SchedulerDefinition.next_run_at <= now,
            )
            .order_by(SchedulerDefinition.next_run_at, SchedulerDefinition.id)
            .limit(limit)
        )
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        return list(self.session.scalars(stmt).all())

    def active_schedule_run(self, schedule_id: int) -> Optional[SchedulerRun]:
        return self.session.scalars(
            select(SchedulerRun).where(
                SchedulerRun.tenant_id == self.ctx.tenant_id,
                SchedulerRun.schedule_id == int(schedule_id),
                SchedulerRun.status == "RUNNING",
            )
        ).first()

    def run_by_key(self, idempotency_key: str) -> Optional[SchedulerRun]:
        return self.session.scalars(
            select(SchedulerRun).where(
                SchedulerRun.tenant_id == self.ctx.tenant_id,
                SchedulerRun.idempotency_key == idempotency_key,
            )
        ).first()

    def add_run(self, **values: Any) -> SchedulerRun:
        row = SchedulerRun(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def list_runs(self, *, schedule_id: Optional[int], limit: int) -> Sequence[SchedulerRun]:
        stmt = select(SchedulerRun).where(SchedulerRun.tenant_id == self.ctx.tenant_id)
        if schedule_id is not None:
            stmt = stmt.where(SchedulerRun.schedule_id == int(schedule_id))
        return list(
            self.session.scalars(stmt.order_by(SchedulerRun.id.desc()).limit(limit)).all()
        )

    def stale_runs(self, *, before: datetime, limit: int) -> Sequence[SchedulerRun]:
        stmt = (
            select(SchedulerRun)
            .where(
                SchedulerRun.tenant_id == self.ctx.tenant_id,
                SchedulerRun.status == "RUNNING",
                SchedulerRun.heartbeat_at < before,
            )
            .order_by(SchedulerRun.id)
            .limit(limit)
        )
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        return list(self.session.scalars(stmt).all())

    # Layouts --------------------------------------------------------------

    def user_layout(self, user_id: int, *, for_update: bool = False) -> Optional[WorkbenchLayout]:
        stmt = select(WorkbenchLayout).where(
            WorkbenchLayout.tenant_id == self.ctx.tenant_id,
            WorkbenchLayout.owner_user_id == int(user_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def role_layout(self, role_id: int, *, for_update: bool = False) -> Optional[WorkbenchLayout]:
        stmt = select(WorkbenchLayout).where(
            WorkbenchLayout.tenant_id == self.ctx.tenant_id,
            WorkbenchLayout.role_id == int(role_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def layout_roles(self) -> Sequence[tuple[Role, Optional[WorkbenchLayout]]]:
        return list(
            self.session.execute(
                select(Role, WorkbenchLayout)
                .outerjoin(
                    WorkbenchLayout,
                    and_(
                        WorkbenchLayout.tenant_id == Role.tenant_id,
                        WorkbenchLayout.role_id == Role.id,
                    ),
                )
                .where(
                    Role.tenant_id == self.ctx.tenant_id,
                    Role.status == "ACTIVE",
                )
                .order_by(Role.code, Role.id)
            ).all()
        )

    def effective_role_layout(self, user_id: int) -> Optional[WorkbenchLayout]:
        return self.session.scalars(
            select(WorkbenchLayout)
            .join(UserRole, UserRole.role_id == WorkbenchLayout.role_id)
            .where(
                WorkbenchLayout.tenant_id == self.ctx.tenant_id,
                UserRole.tenant_id == self.ctx.tenant_id,
                UserRole.user_id == int(user_id),
                WorkbenchLayout.is_active.is_(True),
            )
            .order_by(WorkbenchLayout.priority, WorkbenchLayout.id)
        ).first()

    def effective_layout(self, user_id: int) -> Optional[WorkbenchLayout]:
        """Resolve the active personal/role layout with personal precedence in one query."""

        personal_id = (
            select(WorkbenchLayout.id)
            .where(
                WorkbenchLayout.tenant_id == self.ctx.tenant_id,
                WorkbenchLayout.owner_user_id == int(user_id),
                WorkbenchLayout.is_active.is_(True),
            )
            .order_by(WorkbenchLayout.id)
            .limit(1)
            .correlate(None)
            .scalar_subquery()
        )
        role_id = (
            select(WorkbenchLayout.id)
            .join(UserRole, UserRole.role_id == WorkbenchLayout.role_id)
            .where(
                WorkbenchLayout.tenant_id == self.ctx.tenant_id,
                UserRole.tenant_id == self.ctx.tenant_id,
                UserRole.user_id == int(user_id),
                WorkbenchLayout.is_active.is_(True),
            )
            .order_by(WorkbenchLayout.id)
            .limit(1)
            .correlate(None)
            .scalar_subquery()
        )
        preferred_id = func.coalesce(personal_id, role_id)
        return self.session.scalars(
            select(WorkbenchLayout).where(
                WorkbenchLayout.tenant_id == self.ctx.tenant_id,
                WorkbenchLayout.id == preferred_id,
            )
        ).first()

    def add_layout(self, **values: Any) -> WorkbenchLayout:
        row = WorkbenchLayout(tenant_id=self.ctx.tenant_id, **values)
        self.session.add(row)
        self.session.flush()
        return row

    def widgets(self, layout_id: int) -> Sequence[WorkbenchWidget]:
        return list(
            self.session.scalars(
                select(WorkbenchWidget)
                .where(
                    WorkbenchWidget.tenant_id == self.ctx.tenant_id,
                    WorkbenchWidget.layout_id == int(layout_id),
                )
                .order_by(WorkbenchWidget.sort_order, WorkbenchWidget.id)
            ).all()
        )

    def replace_widgets(self, layout_id: int, widgets: Sequence[dict[str, Any]]) -> None:
        self.session.execute(
            delete(WorkbenchWidget).where(
                WorkbenchWidget.tenant_id == self.ctx.tenant_id,
                WorkbenchWidget.layout_id == int(layout_id),
            )
        )
        for index, values in enumerate(widgets):
            self.session.add(
                WorkbenchWidget(
                    tenant_id=self.ctx.tenant_id,
                    layout_id=int(layout_id),
                    sort_order=index,
                    **values,
                )
            )
        self.session.flush()

    def delete_user_layout(self, user_id: int) -> bool:
        row = self.user_layout(user_id, for_update=True)
        if row is None:
            return False
        self.session.delete(row)
        self.session.flush()
        return True

    def automation_health(self) -> dict[str, int]:
        dead = (
            select(func.count())
            .select_from(EventConsumerLog)
            .where(
                EventConsumerLog.tenant_id == self.ctx.tenant_id,
                EventConsumerLog.status == "DEAD",
            )
            .correlate(None)
            .scalar_subquery()
        )
        retry = (
            select(func.count())
            .select_from(EventConsumerLog)
            .where(
                EventConsumerLog.tenant_id == self.ctx.tenant_id,
                EventConsumerLog.status == "RETRY",
            )
            .correlate(None)
            .scalar_subquery()
        )
        failed_runs = (
            select(func.count())
            .select_from(SchedulerRun)
            .where(
                SchedulerRun.tenant_id == self.ctx.tenant_id,
                SchedulerRun.status.in_(("FAILED", "TIMED_OUT")),
            )
            .correlate(None)
            .scalar_subquery()
        )
        active_rules = (
            select(func.count())
            .select_from(AutomationRuleVersion)
            .where(
                AutomationRuleVersion.tenant_id == self.ctx.tenant_id,
                AutomationRuleVersion.status == "PUBLISHED",
            )
            .correlate(None)
            .scalar_subquery()
        )
        counts = self.session.execute(select(dead, retry, failed_runs, active_rules)).one()
        return {
            "dead_letters": int(counts[0] or 0),
            "retrying_consumers": int(counts[1] or 0),
            "failed_runs": int(counts[2] or 0),
            "published_rules": int(counts[3] or 0),
        }
