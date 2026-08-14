"""Tenant- and park-scoped persistence for facility management."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.facility_management import (
    FacilityDevice,
    FacilityDeviceHistory,
    InspectionException,
    InspectionResult,
    InspectionSchedule,
    InspectionTask,
    InspectionTaskEvent,
    InspectionTemplate,
    InspectionTemplateItem,
    InspectionTemplateVersion,
    IoTAlarm,
    IoTAlarmEscalation,
    IoTAlarmEvent,
    IoTBindingHistory,
    IoTDeviceBinding,
    IoTProvider,
)
from app.infrastructure.database.models.identity import User, UserParkScope
from app.infrastructure.database.models.park_property import Park, Unit
from app.shared.tenant_context import ParkScopeMode, TenantContext


class FacilityManagementRepository:
    """Only persistence boundary used by the facility-management application service."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        return int(self.ctx.tenant_id)

    def _scope(self, stmt, model):  # type: ignore[no-untyped-def]
        stmt = stmt.where(model.tenant_id == self.tenant_id)
        if not hasattr(model, "park_id"):
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            return stmt.where(model.park_id.in_(list(self.ctx.park_ids)))
        return stmt.where(False)

    def _add(self, model):  # type: ignore[no-untyped-def]
        model.tenant_id = self.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model):  # type: ignore[no-untyped-def]
        if int(model.tenant_id) != self.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        if hasattr(model, "park_id") and not self.ctx.allows_park(int(model.park_id)):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model

    def park_exists(self, park_id: int) -> bool:
        return bool(
            self.session.scalar(
                select(Park.id).where(Park.tenant_id == self.tenant_id, Park.id == int(park_id))
            )
        )

    def unit_in_park(self, unit_id: int, park_id: int) -> Unit | None:
        return self.session.scalar(
            select(Unit).where(
                Unit.tenant_id == self.tenant_id,
                Unit.park_id == int(park_id),
                Unit.id == int(unit_id),
                Unit.deleted_at.is_(None),
            )
        )

    def active_user_allows_park(self, user_id: int, park_id: int) -> bool:
        user = self.session.scalar(
            select(User).where(
                User.tenant_id == self.tenant_id,
                User.id == int(user_id),
                User.status == "ACTIVE",
            )
        )
        if user is None:
            return False
        if bool(user.all_parks):
            return True
        return bool(
            self.session.scalar(
                select(UserParkScope.id).where(
                    UserParkScope.tenant_id == self.tenant_id,
                    UserParkScope.user_id == int(user_id),
                    UserParkScope.park_id == int(park_id),
                )
            )
        )

    # Device registry
    def list_devices(
        self,
        *,
        offset: int,
        limit: int,
        park_id: int | None = None,
        status: str | None = None,
        device_type: str | None = None,
    ) -> Sequence[FacilityDevice]:
        stmt = self._scope(select(FacilityDevice), FacilityDevice)
        if park_id is not None:
            stmt = stmt.where(FacilityDevice.park_id == int(park_id))
        if status:
            stmt = stmt.where(FacilityDevice.status == status)
        if device_type:
            stmt = stmt.where(FacilityDevice.device_type == device_type)
        return list(
            self.session.scalars(
                stmt.order_by(FacilityDevice.park_id, FacilityDevice.device_code)
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def count_devices(
        self,
        *,
        park_id: int | None = None,
        status: str | None = None,
        device_type: str | None = None,
    ) -> int:
        stmt = self._scope(select(FacilityDevice.id), FacilityDevice)
        if park_id is not None:
            stmt = stmt.where(FacilityDevice.park_id == int(park_id))
        if status:
            stmt = stmt.where(FacilityDevice.status == status)
        if device_type:
            stmt = stmt.where(FacilityDevice.device_type == device_type)
        return int(self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    def get_device(self, device_id: int, *, for_update: bool = False) -> FacilityDevice | None:
        stmt = self._scope(
            select(FacilityDevice).where(FacilityDevice.id == int(device_id)), FacilityDevice
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def create_device(self, **values: Any) -> FacilityDevice:
        return self._add(FacilityDevice(**values))

    def create_device_history(self, **values: Any) -> FacilityDeviceHistory:
        return self._add(FacilityDeviceHistory(**values))

    def device_history(self, device_id: int) -> Sequence[FacilityDeviceHistory]:
        return list(
            self.session.scalars(
                self._scope(
                    select(FacilityDeviceHistory).where(
                        FacilityDeviceHistory.device_id == int(device_id)
                    ),
                    FacilityDeviceHistory,
                ).order_by(FacilityDeviceHistory.version_no)
            ).all()
        )

    def device_retirement_blockers(self, device_id: int) -> dict[str, int]:
        """Return scoped active references that make retirement unsafe."""

        schedules = int(
            self.session.scalar(
                select(func.count(InspectionSchedule.id)).where(
                    InspectionSchedule.tenant_id == self.tenant_id,
                    InspectionSchedule.device_id == int(device_id),
                    InspectionSchedule.status == "ACTIVE",
                )
            )
            or 0
        )
        tasks = int(
            self.session.scalar(
                select(func.count(InspectionTask.id)).where(
                    InspectionTask.tenant_id == self.tenant_id,
                    InspectionTask.device_id == int(device_id),
                    InspectionTask.status.in_(("PENDING", "IN_PROGRESS")),
                )
            )
            or 0
        )
        alarms = int(
            self.session.scalar(
                select(func.count(IoTAlarm.id)).where(
                    IoTAlarm.tenant_id == self.tenant_id,
                    IoTAlarm.device_id == int(device_id),
                    IoTAlarm.status.in_(("OPEN", "ACKNOWLEDGED")),
                )
            )
            or 0
        )
        bindings = int(
            self.session.scalar(
                select(func.count(IoTDeviceBinding.id)).where(
                    IoTDeviceBinding.tenant_id == self.tenant_id,
                    IoTDeviceBinding.device_id == int(device_id),
                    IoTDeviceBinding.status == "ACTIVE",
                )
            )
            or 0
        )
        return {
            "active_schedules": schedules,
            "active_tasks": tasks,
            "active_alarms": alarms,
            "active_bindings": bindings,
        }

    # Versioned inspection templates
    def list_templates(self) -> Sequence[InspectionTemplate]:
        return list(
            self.session.scalars(
                select(InspectionTemplate)
                .where(InspectionTemplate.tenant_id == self.tenant_id)
                .order_by(InspectionTemplate.code)
            ).all()
        )

    def get_template(self, template_id: int, *, for_update: bool = False) -> InspectionTemplate | None:
        stmt = select(InspectionTemplate).where(
            InspectionTemplate.tenant_id == self.tenant_id,
            InspectionTemplate.id == int(template_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def create_template(self, **values: Any) -> InspectionTemplate:
        return self._add(InspectionTemplate(**values))

    def create_template_version(self, **values: Any) -> InspectionTemplateVersion:
        return self._add(InspectionTemplateVersion(**values))

    def get_template_version(
        self, version_id: int, *, for_update: bool = False
    ) -> InspectionTemplateVersion | None:
        stmt = select(InspectionTemplateVersion).where(
            InspectionTemplateVersion.tenant_id == self.tenant_id,
            InspectionTemplateVersion.id == int(version_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def versions_for_template(self, template_id: int) -> Sequence[InspectionTemplateVersion]:
        return list(
            self.session.scalars(
                select(InspectionTemplateVersion)
                .where(
                    InspectionTemplateVersion.tenant_id == self.tenant_id,
                    InspectionTemplateVersion.template_id == int(template_id),
                )
                .order_by(InspectionTemplateVersion.version_no.desc())
            ).all()
        )

    def create_template_item(self, **values: Any) -> InspectionTemplateItem:
        return self._add(InspectionTemplateItem(**values))

    def template_items(self, version_id: int) -> Sequence[InspectionTemplateItem]:
        return list(
            self.session.scalars(
                select(InspectionTemplateItem)
                .where(
                    InspectionTemplateItem.tenant_id == self.tenant_id,
                    InspectionTemplateItem.template_version_id == int(version_id),
                )
                .order_by(InspectionTemplateItem.position)
            ).all()
        )

    # Weekly schedules and immutable task snapshots
    def list_schedules(self, *, park_id: int | None = None) -> Sequence[InspectionSchedule]:
        stmt = self._scope(select(InspectionSchedule), InspectionSchedule)
        if park_id is not None:
            stmt = stmt.where(InspectionSchedule.park_id == int(park_id))
        return list(self.session.scalars(stmt.order_by(InspectionSchedule.code)).all())

    def active_schedules(self) -> Sequence[InspectionSchedule]:
        return list(
            self.session.scalars(
                self._scope(
                    select(InspectionSchedule).where(InspectionSchedule.status == "ACTIVE"),
                    InspectionSchedule,
                ).order_by(InspectionSchedule.id)
            ).all()
        )

    def get_schedule(
        self, schedule_id: int, *, for_update: bool = False
    ) -> InspectionSchedule | None:
        stmt = self._scope(
            select(InspectionSchedule).where(InspectionSchedule.id == int(schedule_id)),
            InspectionSchedule,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def create_schedule(self, **values: Any) -> InspectionSchedule:
        return self._add(InspectionSchedule(**values))

    def task_for_window(self, schedule_id: int, window_start: datetime) -> InspectionTask | None:
        return self.session.scalar(
            self._scope(
                select(InspectionTask).where(
                    InspectionTask.schedule_id == int(schedule_id),
                    InspectionTask.window_start == window_start,
                ),
                InspectionTask,
            )
        )

    def create_task(self, **values: Any) -> InspectionTask:
        return self._add(InspectionTask(**values))

    def list_tasks(
        self,
        *,
        offset: int,
        limit: int,
        park_id: int | None = None,
        status: str | None = None,
        assignee_user_id: int | None = None,
    ) -> Sequence[InspectionTask]:
        stmt = self._scope(select(InspectionTask), InspectionTask)
        if park_id is not None:
            stmt = stmt.where(InspectionTask.park_id == int(park_id))
        if status:
            stmt = stmt.where(InspectionTask.status == status)
        if assignee_user_id is not None:
            stmt = stmt.where(InspectionTask.assignee_user_id == int(assignee_user_id))
        return list(
            self.session.scalars(
                stmt.order_by(InspectionTask.window_due_at.desc()).offset(offset).limit(limit)
            ).all()
        )

    def count_tasks(
        self,
        *,
        park_id: int | None = None,
        status: str | None = None,
        assignee_user_id: int | None = None,
    ) -> int:
        stmt = self._scope(select(InspectionTask.id), InspectionTask)
        if park_id is not None:
            stmt = stmt.where(InspectionTask.park_id == int(park_id))
        if status:
            stmt = stmt.where(InspectionTask.status == status)
        if assignee_user_id is not None:
            stmt = stmt.where(InspectionTask.assignee_user_id == int(assignee_user_id))
        return int(self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    def get_task(self, task_id: int, *, for_update: bool = False) -> InspectionTask | None:
        stmt = self._scope(
            select(InspectionTask).where(InspectionTask.id == int(task_id)), InspectionTask
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def task_event_by_key(self, key: str) -> InspectionTaskEvent | None:
        return self.session.scalar(
            select(InspectionTaskEvent).where(
                InspectionTaskEvent.tenant_id == self.tenant_id,
                InspectionTaskEvent.idempotency_key == key,
            )
        )

    def create_task_event(self, **values: Any) -> InspectionTaskEvent:
        return self._add(InspectionTaskEvent(**values))

    def task_events(self, task_id: int) -> Sequence[InspectionTaskEvent]:
        return list(
            self.session.scalars(
                self._scope(
                    select(InspectionTaskEvent).where(InspectionTaskEvent.task_id == int(task_id)),
                    InspectionTaskEvent,
                ).order_by(InspectionTaskEvent.occurred_at, InspectionTaskEvent.id)
            ).all()
        )

    def create_result(self, **values: Any) -> InspectionResult:
        return self._add(InspectionResult(**values))

    def task_results(self, task_id: int) -> Sequence[InspectionResult]:
        return list(
            self.session.scalars(
                self._scope(
                    select(InspectionResult).where(InspectionResult.task_id == int(task_id)),
                    InspectionResult,
                ).order_by(InspectionResult.position)
            ).all()
        )

    def create_exception(self, **values: Any) -> InspectionException:
        return self._add(InspectionException(**values))

    def get_exception(
        self, exception_id: int, *, for_update: bool = False
    ) -> InspectionException | None:
        stmt = self._scope(
            select(InspectionException).where(InspectionException.id == int(exception_id)),
            InspectionException,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def task_exceptions(self, task_id: int) -> Sequence[InspectionException]:
        return list(
            self.session.scalars(
                self._scope(
                    select(InspectionException).where(InspectionException.task_id == int(task_id)),
                    InspectionException,
                ).order_by(InspectionException.id)
            ).all()
        )

    def overdue_tasks(self, as_of: datetime) -> Sequence[InspectionTask]:
        return list(
            self.session.scalars(
                self._scope(
                    select(InspectionTask).where(
                        InspectionTask.status.in_(("PENDING", "IN_PROGRESS")),
                        InspectionTask.window_due_at < as_of,
                    ),
                    InspectionTask,
                ).order_by(InspectionTask.window_due_at)
            ).all()
        )

    # IoT providers, bindings and alarm lifecycle
    def list_providers(self) -> Sequence[IoTProvider]:
        return list(
            self.session.scalars(
                select(IoTProvider)
                .where(IoTProvider.tenant_id == self.tenant_id)
                .order_by(IoTProvider.code)
            ).all()
        )

    def get_provider(self, provider_id: int, *, for_update: bool = False) -> IoTProvider | None:
        stmt = select(IoTProvider).where(
            IoTProvider.tenant_id == self.tenant_id,
            IoTProvider.id == int(provider_id),
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def create_provider(self, **values: Any) -> IoTProvider:
        return self._add(IoTProvider(**values))

    def list_bindings(self, *, provider_id: int | None = None) -> Sequence[IoTDeviceBinding]:
        stmt = self._scope(select(IoTDeviceBinding), IoTDeviceBinding)
        if provider_id is not None:
            stmt = stmt.where(IoTDeviceBinding.provider_id == int(provider_id))
        return list(self.session.scalars(stmt.order_by(IoTDeviceBinding.id.desc())).all())

    def get_binding(
        self, binding_id: int, *, for_update: bool = False
    ) -> IoTDeviceBinding | None:
        stmt = self._scope(
            select(IoTDeviceBinding).where(IoTDeviceBinding.id == int(binding_id)),
            IoTDeviceBinding,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def active_binding_by_external_key(
        self, provider_id: int, external_device_key: str, *, for_update: bool = False
    ) -> IoTDeviceBinding | None:
        stmt = self._scope(
            select(IoTDeviceBinding).where(
                IoTDeviceBinding.provider_id == int(provider_id),
                IoTDeviceBinding.external_device_key == external_device_key,
                IoTDeviceBinding.status == "ACTIVE",
            ),
            IoTDeviceBinding,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def create_binding(self, **values: Any) -> IoTDeviceBinding:
        return self._add(IoTDeviceBinding(**values))

    def create_binding_history(self, **values: Any) -> IoTBindingHistory:
        return self._add(IoTBindingHistory(**values))

    def binding_history(self, binding_id: int) -> Sequence[IoTBindingHistory]:
        return list(
            self.session.scalars(
                select(IoTBindingHistory)
                .where(
                    IoTBindingHistory.tenant_id == self.tenant_id,
                    IoTBindingHistory.binding_id == int(binding_id),
                )
                .order_by(IoTBindingHistory.version_no)
            ).all()
        )

    def source_event(self, provider_id: int, source_event_id: str) -> IoTAlarmEvent | None:
        return self.session.scalar(
            select(IoTAlarmEvent).where(
                IoTAlarmEvent.tenant_id == self.tenant_id,
                IoTAlarmEvent.provider_id == int(provider_id),
                IoTAlarmEvent.source_event_id == source_event_id,
            )
        )

    def active_alarm(
        self, binding_id: int, alarm_type: str, *, for_update: bool = False
    ) -> IoTAlarm | None:
        stmt = self._scope(
            select(IoTAlarm).where(
                IoTAlarm.binding_id == int(binding_id),
                IoTAlarm.alarm_type == alarm_type,
                IoTAlarm.status.in_(("OPEN", "ACKNOWLEDGED")),
            ),
            IoTAlarm,
        )
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def create_alarm(self, **values: Any) -> IoTAlarm:
        return self._add(IoTAlarm(**values))

    def create_alarm_event(self, **values: Any) -> IoTAlarmEvent:
        return self._add(IoTAlarmEvent(**values))

    def list_alarms(
        self,
        *,
        offset: int,
        limit: int,
        park_id: int | None = None,
        status: str | None = None,
        severity: str | None = None,
    ) -> Sequence[IoTAlarm]:
        stmt = self._scope(select(IoTAlarm), IoTAlarm)
        if park_id is not None:
            stmt = stmt.where(IoTAlarm.park_id == int(park_id))
        if status:
            stmt = stmt.where(IoTAlarm.status == status)
        if severity:
            stmt = stmt.where(IoTAlarm.severity == severity)
        return list(
            self.session.scalars(
                stmt.order_by(IoTAlarm.last_seen_at.desc()).offset(offset).limit(limit)
            ).all()
        )

    def count_alarms(
        self,
        *,
        park_id: int | None = None,
        status: str | None = None,
        severity: str | None = None,
    ) -> int:
        stmt = self._scope(select(IoTAlarm.id), IoTAlarm)
        if park_id is not None:
            stmt = stmt.where(IoTAlarm.park_id == int(park_id))
        if status:
            stmt = stmt.where(IoTAlarm.status == status)
        if severity:
            stmt = stmt.where(IoTAlarm.severity == severity)
        return int(self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    def get_alarm(self, alarm_id: int, *, for_update: bool = False) -> IoTAlarm | None:
        stmt = self._scope(select(IoTAlarm).where(IoTAlarm.id == int(alarm_id)), IoTAlarm)
        if for_update and self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def alarm_events(self, alarm_id: int) -> Sequence[IoTAlarmEvent]:
        return list(
            self.session.scalars(
                self._scope(
                    select(IoTAlarmEvent).where(IoTAlarmEvent.alarm_id == int(alarm_id)),
                    IoTAlarmEvent,
                ).order_by(IoTAlarmEvent.source_time, IoTAlarmEvent.id)
            ).all()
        )

    def create_escalation(self, **values: Any) -> IoTAlarmEscalation:
        return self._add(IoTAlarmEscalation(**values))

    def alarm_escalations(self, alarm_id: int) -> Sequence[IoTAlarmEscalation]:
        return list(
            self.session.scalars(
                self._scope(
                    select(IoTAlarmEscalation).where(
                        IoTAlarmEscalation.alarm_id == int(alarm_id)
                    ),
                    IoTAlarmEscalation,
                ).order_by(IoTAlarmEscalation.level)
            ).all()
        )

    def alarms_for_escalation(self, as_of: datetime) -> Sequence[IoTAlarm]:
        return list(
            self.session.scalars(
                self._scope(
                    select(IoTAlarm).where(
                        IoTAlarm.status.in_(("OPEN", "ACKNOWLEDGED")),
                        IoTAlarm.severity.in_(("HIGH", "CRITICAL")),
                        IoTAlarm.last_seen_at < as_of,
                    ),
                    IoTAlarm,
                ).order_by(IoTAlarm.last_seen_at)
            ).all()
        )
