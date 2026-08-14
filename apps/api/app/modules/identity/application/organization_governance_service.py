"""平台组织治理应用服务与服务端字段投影。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.identity.infrastructure.organization_governance_repository import (
    OrganizationGovernanceRepository,
)
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)

UTC = timezone.utc

PROTECTED_FIELD_REGISTRY: dict[tuple[str, str], tuple[str, Callable[[Any], Any]]] = {}
_FIELD_PRECEDENCE = {"VISIBLE": 0, "MASKED": 1, "HIDDEN": 2}


def _mask_phone(value: Any) -> Any:
    """确定性脱敏手机号；空值保持空，短值不回显原文。"""

    if value is None:
        return None
    raw = str(value)
    if len(raw) >= 7:
        return f"{raw[:3]}****{raw[-4:]}"
    return "*" * len(raw)


PROTECTED_FIELD_REGISTRY[("USER", "phone")] = ("PHONE", _mask_phone)


def _naive_utc(value: datetime | None, *, default_now: bool = False) -> datetime | None:
    if value is None:
        return utc_now() if default_now else None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


class OrganizationGovernanceService:
    """集团、区域、园区调区、岗位与任职用例编排。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = OrganizationGovernanceRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无组织治理权限", code="PERMISSION_DENIED", status_code=403)

    def _commit_conflict(self, message: str, code: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    def _add_with_conflict(self, row: Any, message: str, code: str) -> Any:
        """Convert both flush-time and commit-time uniqueness failures to 409."""

        try:
            return self.repo.add(row)
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    def _log(self, action: str, resource_id: int | str | None, park_id: int | None = None) -> None:
        log_business_success(
            logger,
            "组织治理操作成功",
            ctx=self.ctx,
            module="organization_governance",
            action=action,
            resource_id=resource_id,
            park_id=park_id,
        )

    def hierarchy(self) -> dict[str, Any]:
        self._require("identity.org_governance.read")
        groups = {int(row.id): self._group_dict(row) for row in self.repo.list_groups()}
        regions: dict[int, dict[str, Any]] = {}
        for row in self.repo.list_regions():
            data = self._region_dict(row)
            data["parks"] = []
            regions[int(row.id)] = data
        for assignment in self.repo.list_current_park_assignments():
            park = self.repo.get_park(int(assignment.park_id))
            if park is None or int(assignment.region_id) not in regions:
                continue
            regions[int(assignment.region_id)]["parks"].append(
                {
                    "id": int(park.id),
                    "name": park.name,
                    "status": park.status,
                    "assignment_id": int(assignment.id),
                    "effective_from": assignment.effective_from.isoformat(),
                }
            )
        result: list[dict[str, Any]] = []
        for group_id, group in groups.items():
            group["regions"] = [
                region
                for region in regions.values()
                if int(region["group_id"]) == group_id
            ]
            result.append(group)
        return {"groups": result}

    def create_group(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("identity.org_governance.write")
        code = str(data["code"]).strip().upper()
        if self.repo.find_group_by_code(code) is not None:
            raise AppError("集团编码重复", code="ORG_GROUP_CODE_DUPLICATE", status_code=409)
        row = self._add_with_conflict(
            self.repo.new_group(
                tenant_id=self.ctx.tenant_id,
                code=code,
                name=str(data["name"]).strip(),
                sort_order=int(data.get("sort_order") or 0),
                remark=data.get("remark"),
            ),
            "集团编码重复",
            "ORG_GROUP_CODE_DUPLICATE",
        )
        self.audit.record(
            action="create",
            resource_type="ORGANIZATION_GROUP",
            resource_id=row.id,
            detail={"code": code},
        )
        self._commit_conflict("集团编码重复", "ORG_GROUP_CODE_DUPLICATE")
        self._log("create_group", row.id)
        return self._group_dict(row)

    def update_group(self, group_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require("identity.org_governance.write")
        row = self.repo.get_group(group_id, for_update=True)
        if row is None:
            raise AppError("集团不存在", code="ORG_GROUP_NOT_FOUND", status_code=404)
        if (
            data.get("status") == "DISABLED"
            and row.status != "DISABLED"
            and self.repo.active_region_count(group_id)
        ):
            raise AppError(
                "集团仍有启用区域",
                code="ORG_GROUP_HAS_ACTIVE_REGIONS",
                status_code=409,
            )
        for field in ("name", "status", "sort_order", "remark"):
            if field in data and data[field] is not None:
                setattr(row, field, str(data[field]).strip() if field == "name" else data[field])
        self.repo.add(row)
        self.audit.record(
            action="update",
            resource_type="ORGANIZATION_GROUP",
            resource_id=row.id,
            detail={"fields": sorted(data)},
        )
        self.session.commit()
        self._log("update_group", row.id)
        return self._group_dict(row)

    def create_region(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("identity.org_governance.write")
        group = self.repo.get_group(int(data["group_id"]))
        if group is None:
            raise AppError("集团不存在", code="ORG_GROUP_NOT_FOUND", status_code=404)
        if group.status != "ACTIVE":
            raise AppError("集团已停用", code="ORG_GROUP_DISABLED", status_code=409)
        code = str(data["code"]).strip().upper()
        if self.repo.find_region_by_code(code) is not None:
            raise AppError("区域编码重复", code="ORG_REGION_CODE_DUPLICATE", status_code=409)
        row = self._add_with_conflict(
            self.repo.new_region(
                tenant_id=self.ctx.tenant_id,
                group_id=int(group.id),
                code=code,
                name=str(data["name"]).strip(),
                sort_order=int(data.get("sort_order") or 0),
                remark=data.get("remark"),
            ),
            "区域编码重复",
            "ORG_REGION_CODE_DUPLICATE",
        )
        self.audit.record(
            action="create",
            resource_type="ORGANIZATION_REGION",
            resource_id=row.id,
            detail={"code": code, "group_id": int(group.id)},
        )
        self._commit_conflict("区域编码重复", "ORG_REGION_CODE_DUPLICATE")
        self._log("create_region", row.id)
        return self._region_dict(row)

    def update_region(self, region_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require("identity.org_governance.write")
        row = self.repo.get_region(region_id, for_update=True)
        if row is None:
            raise AppError("区域不存在", code="ORG_REGION_NOT_FOUND", status_code=404)
        if "group_id" in data and data["group_id"] is not None:
            group = self.repo.get_group(int(data["group_id"]))
            if group is None:
                raise AppError("集团不存在", code="ORG_GROUP_NOT_FOUND", status_code=404)
            if group.status != "ACTIVE":
                raise AppError("集团已停用", code="ORG_GROUP_DISABLED", status_code=409)
            row.group_id = int(group.id)
        if (
            data.get("status") == "DISABLED"
            and row.status != "DISABLED"
            and self.repo.current_park_count(region_id)
        ):
            raise AppError(
                "区域仍有关联园区",
                code="ORG_REGION_HAS_CURRENT_PARKS",
                status_code=409,
            )
        for field in ("name", "status", "sort_order", "remark"):
            if field in data and data[field] is not None:
                setattr(row, field, str(data[field]).strip() if field == "name" else data[field])
        self.repo.add(row)
        self.audit.record(
            action="update",
            resource_type="ORGANIZATION_REGION",
            resource_id=row.id,
            detail={"fields": sorted(data)},
        )
        self.session.commit()
        self._log("update_region", row.id)
        return self._region_dict(row)

    def assign_park(self, data: dict[str, Any]) -> dict[str, Any]:
        """锁定园区与 current 关系，关闭旧行并创建新行。"""

        self._require("identity.org_governance.write")
        park_id = int(data["park_id"])
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        park = self.repo.get_park(park_id, for_update=True)
        if park is None:
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        region = self.repo.get_region(int(data["region_id"]), for_update=True)
        if region is None:
            raise AppError("区域不存在", code="ORG_REGION_NOT_FOUND", status_code=404)
        if region.status != "ACTIVE":
            raise AppError("区域已停用", code="ORG_REGION_DISABLED", status_code=409)
        effective_from = _naive_utc(data.get("effective_from"), default_now=True)
        assert effective_from is not None
        current = self.repo.get_current_park_assignment(park_id, for_update=True)
        if current is not None and int(current.region_id) == int(region.id):
            return self._park_assignment_dict(current)
        previous_region_id = int(current.region_id) if current is not None else None
        if current is not None:
            if effective_from < current.effective_from:
                raise AppError(
                    "生效时间早于当前归属",
                    code="ORG_PARK_EFFECTIVE_TIME_INVALID",
                    status_code=409,
                )
            current.effective_to = effective_from
            current.ended_by = self.ctx.user_id or None
            self.repo.add(current)
        row = self._add_with_conflict(
            self.repo.new_park_assignment(
                tenant_id=self.ctx.tenant_id,
                region_id=int(region.id),
                park_id=park_id,
                effective_from=effective_from,
                assigned_by=self.ctx.user_id or None,
                reason=data.get("reason"),
            ),
            "园区当前归属冲突",
            "ORG_PARK_ASSIGNMENT_CONFLICT",
        )
        self.audit.record(
            action="reassign" if previous_region_id else "assign",
            resource_type="REGION_PARK_ASSIGNMENT",
            resource_id=row.id,
            park_id=park_id,
            detail={
                "previous_region_id": previous_region_id,
                "region_id": int(region.id),
                "effective_from": effective_from.isoformat(),
            },
        )
        self._commit_conflict("园区当前归属冲突", "ORG_PARK_ASSIGNMENT_CONFLICT")
        self._log("assign_park", row.id, park_id)
        return self._park_assignment_dict(row)

    def park_assignment_history(self, park_id: int) -> list[dict[str, Any]]:
        self._require("identity.org_governance.read")
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        if self.repo.get_park(park_id) is None:
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        return [
            self._park_assignment_dict(row)
            for row in self.repo.list_park_assignment_history(park_id)
        ]

    def list_positions(self) -> list[dict[str, Any]]:
        self._require("identity.org_governance.read")
        return [self._position_dict(row) for row in self.repo.list_positions()]

    def create_position(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("identity.org_governance.write")
        code = str(data["code"]).strip().upper()
        if self.repo.find_position_by_code(code) is not None:
            raise AppError("岗位编码重复", code="POSITION_CODE_DUPLICATE", status_code=409)
        org_unit_id = data.get("org_unit_id")
        if org_unit_id is not None and self.repo.get_org_unit(int(org_unit_id)) is None:
            raise AppError("组织不存在", code="ORG_NOT_FOUND", status_code=404)
        row = self._add_with_conflict(
            self.repo.new_position(
                tenant_id=self.ctx.tenant_id,
                org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
                code=code,
                name=str(data["name"]).strip(),
                sort_order=int(data.get("sort_order") or 0),
                responsibilities=data.get("responsibilities"),
            ),
            "岗位编码重复",
            "POSITION_CODE_DUPLICATE",
        )
        self.audit.record(
            action="create",
            resource_type="POSITION",
            resource_id=row.id,
            detail={"code": code, "org_unit_id": row.org_unit_id},
        )
        self._commit_conflict("岗位编码重复", "POSITION_CODE_DUPLICATE")
        self._log("create_position", row.id)
        return self._position_dict(row)

    def update_position(self, position_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require("identity.org_governance.write")
        row = self.repo.get_position(position_id, for_update=True)
        if row is None:
            raise AppError("岗位不存在", code="POSITION_NOT_FOUND", status_code=404)
        if (
            data.get("status") == "DISABLED"
            and row.status != "DISABLED"
            and self.repo.active_assignment_count(position_id)
        ):
            raise AppError(
                "岗位仍有当前任职",
                code="POSITION_HAS_CURRENT_ASSIGNMENTS",
                status_code=409,
            )
        if data.get("clear_org_unit"):
            row.org_unit_id = None
        elif "org_unit_id" in data and data["org_unit_id"] is not None:
            org_unit = self.repo.get_org_unit(int(data["org_unit_id"]))
            if org_unit is None:
                raise AppError("组织不存在", code="ORG_NOT_FOUND", status_code=404)
            row.org_unit_id = int(org_unit.id)
        for field in ("name", "status", "sort_order", "responsibilities"):
            if field in data and data[field] is not None:
                setattr(row, field, str(data[field]).strip() if field == "name" else data[field])
        self.repo.add(row)
        self.audit.record(
            action="update",
            resource_type="POSITION",
            resource_id=row.id,
            detail={"fields": sorted(data)},
        )
        self.session.commit()
        self._log("update_position", row.id)
        return self._position_dict(row)

    def list_user_assignments(
        self, *, user_id: int | None = None, current_only: bool = False
    ) -> list[dict[str, Any]]:
        self._require("identity.org_governance.read")
        if user_id is not None and self.repo.get_user(user_id) is None:
            raise AppError("用户不存在", code="USER_NOT_FOUND", status_code=404)
        return [
            self._assignment_dict(row)
            for row in self.repo.list_user_assignments(
                user_id=user_id,
                current_only=current_only,
            )
        ]

    def assign_user(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("identity.org_governance.write")
        user_id = int(data["user_id"])
        position_id = int(data["position_id"])
        user = self.repo.get_user(user_id)
        if user is None:
            raise AppError("用户不存在", code="USER_NOT_FOUND", status_code=404)
        position = self.repo.get_position(position_id, for_update=True)
        if position is None:
            raise AppError("岗位不存在", code="POSITION_NOT_FOUND", status_code=404)
        if position.status != "ACTIVE":
            raise AppError("岗位已停用", code="POSITION_DISABLED", status_code=409)
        park_id = int(data["park_id"]) if data.get("park_id") is not None else None
        if park_id is not None:
            if not self.ctx.allows_park(park_id):
                raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
            if self.repo.get_park(park_id) is None:
                raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        scope_key = f"PARK:{park_id}" if park_id is not None else "TENANT"
        if self.repo.get_current_duplicate_assignment(
            user_id=user_id,
            position_id=position_id,
            scope_key=scope_key,
        ) is not None:
            raise AppError("当前任职重复", code="POSITION_ASSIGNMENT_DUPLICATE", status_code=409)
        is_primary = bool(data.get("is_primary"))
        if is_primary and self.repo.get_current_primary_assignment(user_id, for_update=True):
            raise AppError("用户已有主岗位", code="PRIMARY_POSITION_CONFLICT", status_code=409)
        authorization_before = self.repo.current_authorization_snapshot(user_id)
        starts_at = _naive_utc(data.get("starts_at"), default_now=True)
        assert starts_at is not None
        row = self._add_with_conflict(
            self.repo.new_user_assignment(
                tenant_id=self.ctx.tenant_id,
                user_id=user_id,
                position_id=position_id,
                park_id=park_id,
                scope_key=scope_key,
                starts_at=starts_at,
                is_primary=is_primary,
                assigned_by=self.ctx.user_id or None,
                remark=data.get("remark"),
            ),
            "任职并发冲突",
            "POSITION_ASSIGNMENT_CONFLICT",
        )
        authorization_after = self.repo.current_authorization_snapshot(user_id)
        if authorization_before != authorization_after:
            self.session.rollback()
            raise AppError(
                "任职不得修改授权关系",
                code="POSITION_AUTHORIZATION_BOUNDARY_BROKEN",
                status_code=500,
            )
        self.audit.record(
            action="assign",
            resource_type="USER_POSITION_ASSIGNMENT",
            resource_id=row.id,
            park_id=park_id,
            detail={
                "user_id": user_id,
                "position_id": position_id,
                "is_primary": is_primary,
            },
        )
        self._commit_conflict("任职并发冲突", "POSITION_ASSIGNMENT_CONFLICT")
        self._log("assign_user", row.id, park_id)
        return self._assignment_dict(row)

    def end_user_assignment(
        self, assignment_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        self._require("identity.org_governance.write")
        row = self.repo.get_user_assignment(assignment_id, for_update=True)
        if row is None:
            raise AppError("任职不存在", code="POSITION_ASSIGNMENT_NOT_FOUND", status_code=404)
        if row.ends_at is not None:
            return self._assignment_dict(row)
        ends_at = _naive_utc(data.get("ends_at"), default_now=True)
        assert ends_at is not None
        if ends_at < row.starts_at:
            raise AppError("结束时间早于开始时间", code="ASSIGNMENT_TIME_INVALID", status_code=409)
        row.ends_at = ends_at
        row.ended_by = self.ctx.user_id or None
        if data.get("remark") is not None:
            row.remark = data["remark"]
        self.repo.add(row)
        self.audit.record(
            action="end",
            resource_type="USER_POSITION_ASSIGNMENT",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"ends_at": ends_at.isoformat()},
        )
        self.session.commit()
        self._log("end_user_assignment", row.id, row.park_id)
        return self._assignment_dict(row)

    @staticmethod
    def _group_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "code": row.code,
            "name": row.name,
            "status": row.status,
            "sort_order": row.sort_order,
            "remark": row.remark,
        }

    @staticmethod
    def _region_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "group_id": int(row.group_id),
            "code": row.code,
            "name": row.name,
            "status": row.status,
            "sort_order": row.sort_order,
            "remark": row.remark,
        }

    @staticmethod
    def _park_assignment_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "region_id": int(row.region_id),
            "park_id": int(row.park_id),
            "effective_from": row.effective_from.isoformat(),
            "effective_to": row.effective_to.isoformat() if row.effective_to else None,
            "assigned_by": row.assigned_by,
            "ended_by": row.ended_by,
            "reason": row.reason,
        }

    @staticmethod
    def _position_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "org_unit_id": row.org_unit_id,
            "code": row.code,
            "name": row.name,
            "status": row.status,
            "sort_order": row.sort_order,
            "responsibilities": row.responsibilities,
        }

    @staticmethod
    def _assignment_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "user_id": int(row.user_id),
            "position_id": int(row.position_id),
            "park_id": row.park_id,
            "scope_key": row.scope_key,
            "starts_at": row.starts_at.isoformat(),
            "ends_at": row.ends_at.isoformat() if row.ends_at else None,
            "is_primary": bool(row.is_primary),
            "assigned_by": row.assigned_by,
            "ended_by": row.ended_by,
            "remark": row.remark,
        }


class FieldAccessService:
    """按请求用户的数据库角色解析受保护字段，并在序列化前投影。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.ctx = ctx
        self.repo = OrganizationGovernanceRepository(session, ctx)

    @staticmethod
    def protected_fields() -> list[dict[str, str]]:
        return [
            {
                "resource_type": resource,
                "field_name": field,
                "mask_strategy": strategy,
            }
            for (resource, field), (strategy, _) in sorted(PROTECTED_FIELD_REGISTRY.items())
        ]

    def resolved_modes(self, resource_type: str) -> dict[str, str]:
        resource = resource_type.strip().upper()
        protected = {
            field
            for (registered_resource, field) in PROTECTED_FIELD_REGISTRY
            if registered_resource == resource
        }
        modes: dict[str, str] = {}
        if not self.ctx.user_id:
            return {field: "MASKED" for field in protected}
        for field_name, access_mode in self.repo.active_field_modes_for_user(
            user_id=int(self.ctx.user_id),
            resource_type=resource,
        ):
            field = str(field_name)
            mode = str(access_mode)
            if field not in protected or mode not in _FIELD_PRECEDENCE:
                continue
            current = modes.get(field)
            if current is None or _FIELD_PRECEDENCE[mode] > _FIELD_PRECEDENCE[current]:
                modes[field] = mode
        return {field: modes.get(field, "MASKED") for field in protected}

    def project_many(
        self, resource_type: str, payloads: Iterable[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        resource = resource_type.strip().upper()
        modes = self.resolved_modes(resource)
        result: list[dict[str, Any]] = []
        for payload in payloads:
            projected = dict(payload)
            for field, mode in modes.items():
                if field not in projected:
                    continue
                if mode == "HIDDEN":
                    projected.pop(field, None)
                elif mode == "MASKED":
                    _, masker = PROTECTED_FIELD_REGISTRY[(resource, field)]
                    projected[field] = masker(projected[field])
            result.append(projected)
        return result


class FieldPolicyAdminService:
    """字段策略管理；策略值来自白名单，不接受任意资源字段。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = OrganizationGovernanceRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无字段策略权限", code="PERMISSION_DENIED", status_code=403)

    def list_policies(self) -> list[dict[str, Any]]:
        self._require("identity.field_policy.read")
        return [self._to_dict(row) for row in self.repo.list_field_policies()]

    def list_protected_fields(self) -> list[dict[str, str]]:
        self._require("identity.field_policy.read")
        return FieldAccessService.protected_fields()

    def upsert_policy(self, data: dict[str, Any]) -> dict[str, Any]:
        self._require("identity.field_policy.write")
        resource_type = str(data["resource_type"]).strip().upper()
        field_name = str(data["field_name"]).strip().lower()
        registry = PROTECTED_FIELD_REGISTRY.get((resource_type, field_name))
        if registry is None:
            raise AppError(
                "字段不在受保护白名单",
                code="FIELD_POLICY_TARGET_INVALID",
                status_code=400,
            )
        expected_strategy, _ = registry
        mask_strategy = str(data.get("mask_strategy") or expected_strategy).strip().upper()
        if mask_strategy != expected_strategy:
            raise AppError(
                "脱敏策略与字段不匹配",
                code="FIELD_MASK_STRATEGY_INVALID",
                status_code=400,
            )
        role_id = int(data["role_id"])
        if self.repo.get_role(role_id) is None:
            raise AppError("角色不存在", code="ROLE_NOT_FOUND", status_code=404)
        row = self.repo.find_field_policy(
            role_id=role_id,
            resource_type=resource_type,
            field_name=field_name,
        )
        created = row is None
        if row is None:
            row = self.repo.new_field_policy(
                tenant_id=self.ctx.tenant_id,
                role_id=role_id,
                resource_type=resource_type,
                field_name=field_name,
                access_mode=str(data["access_mode"]),
                mask_strategy=mask_strategy,
                status=str(data.get("status") or "ACTIVE"),
            )
        else:
            row.access_mode = str(data["access_mode"])
            row.mask_strategy = mask_strategy
            row.status = str(data.get("status") or "ACTIVE")
        try:
            self.repo.add(row)
            self.audit.record(
                action="create" if created else "update",
                resource_type="FIELD_ACCESS_POLICY",
                resource_id=row.id,
                detail={
                    "role_id": role_id,
                    "resource_type": resource_type,
                    "field_name": field_name,
                    "access_mode": row.access_mode,
                    "status": row.status,
                },
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "字段策略并发冲突",
                code="FIELD_POLICY_CONFLICT",
                status_code=409,
            ) from exc
        log_business_success(
            logger,
            "字段策略保存成功",
            ctx=self.ctx,
            module="organization_governance",
            action="upsert_field_policy",
            resource_id=row.id,
        )
        return self._to_dict(row)

    @staticmethod
    def _to_dict(row: Any) -> dict[str, Any]:
        return {
            "id": int(row.id),
            "role_id": int(row.role_id),
            "resource_type": row.resource_type,
            "field_name": row.field_name,
            "access_mode": row.access_mode,
            "mask_strategy": row.mask_strategy,
            "status": row.status,
        }
