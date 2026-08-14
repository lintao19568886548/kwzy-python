"""REST endpoints for governed facility devices, inspections and IoT alarms."""

# FastAPI's declarative dependency defaults intentionally call Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db
from app.modules.facility_ops.application.facility_management_service import (
    FacilityManagementService,
)
from app.modules.facility_ops.interface.facility_management_schemas import (
    AlarmTransition,
    DeviceCreate,
    DeviceUpdate,
    ExpectedReason,
    ExpectedVersion,
    InspectionReassign,
    InspectionScheduleCreate,
    InspectionSubmit,
    InspectionTemplateCreate,
    InspectionTemplateVersionCreate,
    IoTAlarmIngest,
    IoTBindingCreate,
    IoTProviderCreate,
    ReasonBody,
    SweepRequest,
)
from app.shared.deps import get_tenant_context, require_permissions
from app.shared.response import ok
from app.shared.tenant_context import TenantContext

router = APIRouter(tags=["FacilityManagement"])
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def _svc(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> FacilityManagementService:
    return FacilityManagementService(db, ctx)


@router.get("/facility-devices", dependencies=[Depends(require_permissions("facility_device:read"))])
def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    park_id: int | None = None,
    status: str | None = None,
    device_type: str | None = None,
    svc: FacilityManagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_devices(
            page=page,
            page_size=page_size,
            park_id=park_id,
            status=status,
            kind=device_type,
        )
    )


@router.post("/facility-devices", dependencies=[Depends(require_permissions("facility_device:write"))])
def create_device(body: DeviceCreate, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.create_device(body.model_dump()), message="created")


@router.get(
    "/facility-devices/{device_id}",
    dependencies=[Depends(require_permissions("facility_device:read"))],
)
def get_device(device_id: int, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.get_device(device_id))


@router.put(
    "/facility-devices/{device_id}",
    dependencies=[Depends(require_permissions("facility_device:write"))],
)
def update_device(
    device_id: int, body: DeviceUpdate, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.update_device(device_id, body.model_dump(exclude_unset=True)), message="updated")


@router.post(
    "/facility-devices/{device_id}/retire",
    dependencies=[Depends(require_permissions("facility_device:retire"))],
)
def retire_device(
    device_id: int, body: ExpectedReason, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.retire_device(device_id, body.model_dump()), message="retired")


@router.get("/inspection-templates")
def list_templates(svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.list_templates())


@router.post(
    "/inspection-templates",
    dependencies=[Depends(require_permissions("inspection:template_manage"))],
)
def create_template(
    body: InspectionTemplateCreate, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.create_template(body.model_dump()), message="created")


@router.post(
    "/inspection-templates/{template_id}/versions",
    dependencies=[Depends(require_permissions("inspection:template_manage"))],
)
def add_template_version(
    template_id: int,
    body: InspectionTemplateVersionCreate,
    svc: FacilityManagementService = Depends(_svc),
) -> dict:
    return ok(svc.add_template_version(template_id, body.model_dump()), message="created")


@router.post(
    "/inspection-template-versions/{version_id}/publish",
    dependencies=[Depends(require_permissions("inspection:template_manage"))],
)
def publish_template_version(
    version_id: int,
    body: ExpectedVersion,
    svc: FacilityManagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.publish_template_version(version_id, expected_version=body.expected_version),
        message="published",
    )


@router.get("/inspection-schedules")
def list_schedules(
    park_id: int | None = None, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.list_schedules(park_id=park_id))


@router.post(
    "/inspection-schedules",
    dependencies=[Depends(require_permissions("inspection:schedule_manage"))],
)
def create_schedule(
    body: InspectionScheduleCreate, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.create_schedule(body.model_dump()), message="created")


@router.post(
    "/inspection-schedules/{schedule_id}/retire",
    dependencies=[Depends(require_permissions("inspection:schedule_manage"))],
)
def retire_schedule(
    schedule_id: int, body: ExpectedReason, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.retire_schedule(schedule_id, body.model_dump()), message="retired")


@router.post(
    "/inspection-schedules/{schedule_id}/pause",
    dependencies=[Depends(require_permissions("inspection:schedule_manage"))],
)
def pause_schedule(
    schedule_id: int, body: ExpectedReason, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.transition_schedule(schedule_id, "PAUSED", body.model_dump()), message="paused")


@router.post(
    "/inspection-schedules/{schedule_id}/resume",
    dependencies=[Depends(require_permissions("inspection:schedule_manage"))],
)
def resume_schedule(
    schedule_id: int, body: ExpectedReason, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.transition_schedule(schedule_id, "ACTIVE", body.model_dump()), message="resumed")


@router.post(
    "/inspection-tasks/generate",
    dependencies=[Depends(require_permissions("inspection:sweep"))],
)
def generate_tasks(body: SweepRequest, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.generate_tasks(as_of=body.as_of), message="generated")


@router.post(
    "/inspection-tasks/sweep-missed",
    dependencies=[Depends(require_permissions("inspection:sweep"))],
)
def sweep_missed(body: SweepRequest, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.sweep_missed(as_of=body.as_of), message="swept")


@router.get("/inspection-tasks")
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    park_id: int | None = None,
    status: str | None = None,
    assignee_user_id: int | None = None,
    svc: FacilityManagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_tasks(
            page=page,
            page_size=page_size,
            park_id=park_id,
            status=status,
            assignee_user_id=assignee_user_id,
        )
    )


@router.get("/inspection-tasks/{task_id}")
def get_task(task_id: int, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.get_task(task_id))


@router.post(
    "/inspection-tasks/{task_id}/start",
    dependencies=[Depends(require_permissions("inspection:execute"))],
)
def start_task(
    task_id: int,
    body: ExpectedVersion,
    idempotency_key: IdempotencyKey,
    svc: FacilityManagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.start_task(task_id, expected_version=body.expected_version, key=idempotency_key),
        message="started",
    )


@router.post(
    "/inspection-tasks/{task_id}/reassign",
    dependencies=[Depends(require_permissions("inspection:dispatch"))],
)
def reassign_task(
    task_id: int, body: InspectionReassign, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.reassign_task(task_id, body.model_dump()), message="reassigned")


@router.post(
    "/inspection-tasks/{task_id}/submit",
    dependencies=[Depends(require_permissions("inspection:execute"))],
)
def submit_task(
    task_id: int,
    body: InspectionSubmit,
    idempotency_key: IdempotencyKey,
    svc: FacilityManagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.submit_task(task_id, body.model_dump(), key=idempotency_key), message="submitted"
    )


@router.post(
    "/inspection-exceptions/{exception_id}/promote",
    dependencies=[Depends(require_permissions("inspection:dispatch"))],
)
def promote_exception(
    exception_id: int, body: ReasonBody, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.promote_exception(exception_id, body.model_dump()), message="promoted")


@router.get("/iot-providers")
def list_providers(svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.list_providers())


@router.post(
    "/iot-providers",
    dependencies=[Depends(require_permissions("iot:provider_manage"))],
)
def create_provider(body: IoTProviderCreate, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.create_provider(body.model_dump()), message="created")


@router.get("/iot-device-bindings")
def list_bindings(
    provider_id: int | None = None, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.list_bindings(provider_id=provider_id))


@router.post(
    "/iot-device-bindings",
    dependencies=[Depends(require_permissions("iot:binding_manage"))],
)
def create_binding(body: IoTBindingCreate, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.create_binding(body.model_dump()), message="created")


@router.post(
    "/iot-device-bindings/{binding_id}/retire",
    dependencies=[Depends(require_permissions("iot:binding_manage"))],
)
def retire_binding(
    binding_id: int, body: ExpectedReason, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.retire_binding(binding_id, body.model_dump()), message="retired")


@router.post(
    "/iot-alarm-events/ingest",
    dependencies=[Depends(require_permissions("iot:ingest"))],
)
def ingest_alarm(body: IoTAlarmIngest, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.ingest_alarm(body.model_dump()), message="accepted")


@router.post(
    "/iot-alarms/sweep-escalations",
    dependencies=[Depends(require_permissions("iot:alarm_sweep"))],
)
def sweep_alarm_escalations(
    body: SweepRequest, svc: FacilityManagementService = Depends(_svc)
) -> dict:
    return ok(svc.sweep_alarm_escalations(as_of=body.as_of), message="swept")


@router.get("/iot-alarms")
def list_alarms(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    park_id: int | None = None,
    status: str | None = None,
    severity: str | None = None,
    svc: FacilityManagementService = Depends(_svc),
) -> dict:
    return ok(
        svc.list_alarms(
            page=page,
            page_size=page_size,
            park_id=park_id,
            status=status,
            severity=severity,
        )
    )


@router.get("/iot-alarms/{alarm_id}")
def get_alarm(alarm_id: int, svc: FacilityManagementService = Depends(_svc)) -> dict:
    return ok(svc.get_alarm(alarm_id))


@router.post(
    "/iot-alarms/{alarm_id}/{target}",
    dependencies=[Depends(require_permissions("iot:alarm_manage"))],
)
def transition_alarm(
    alarm_id: int,
    target: Literal["acknowledge", "resolve", "close"],
    body: AlarmTransition,
    svc: FacilityManagementService = Depends(_svc),
) -> dict:
    mapped = {"acknowledge": "ACKNOWLEDGED", "resolve": "RESOLVED", "close": "CLOSED"}
    return ok(svc.transition_alarm(alarm_id, mapped[target], body.model_dump()), message=target)
