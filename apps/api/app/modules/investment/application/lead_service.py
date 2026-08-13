"""功能说明：招商线索应用服务（创建/跟进/输单/转化）。"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.investment.domain.rules import (
    CONVERTIBLE,
    assert_status_transition,
    normalize_intent_level,
    normalize_phone,
)
from app.modules.investment.infrastructure.lead_repository import LeadRepository
from app.modules.lease.application.lease_service import LeaseService
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.party.application.party_service import PartyService
from app.modules.workbench.application.work_item_service import WorkItemService
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)

LEAD_FOLLOW_ITEM_TYPE = "LEAD_FOLLOW"


class LeadService:
    """功能说明：编排线索生命周期；转化时创建主体与可选合同草稿。"""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.leads = LeadRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.parties = PartyService(session, ctx)
        self.leases = LeaseService(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require(self, lead_id: int, *, for_update: bool = False):
        m = self.leads.get_by_id(lead_id, for_update=for_update)
        if m is None:
            raise AppError("线索不存在", code="LEAD_NOT_FOUND", status_code=404)
        return m

    def _assert_park(self, park_id: int) -> int:
        pid = int(park_id)
        if not self.parks.exists_in_tenant(pid):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(pid):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return pid

    def _to_dict(self, model) -> dict[str, Any]:
        return {
            "id": model.id,
            "tenant_id": model.tenant_id,
            "park_id": model.park_id,
            "name": model.name,
            "contact_phone": model.contact_phone,
            "contact_name": model.contact_name,
            "agent_name": model.agent_name,
            "intent_level": model.intent_level,
            "intent_area": str(model.intent_area) if model.intent_area is not None else None,
            "status": model.status,
            "remark": model.remark,
            "owner_user_id": model.owner_user_id,
            "party_id": model.party_id,
            "lease_id": model.lease_id,
            "converted_at": model.converted_at.isoformat() if model.converted_at else None,
            "lost_reason": model.lost_reason,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    def _open_follow_todo(self, model) -> None:
        self.work_items.ensure_from_source(
            source_type="LEAD",
            source_id=str(model.id),
            item_type=LEAD_FOLLOW_ITEM_TYPE,
            title=f"跟进线索 {model.name}",
            description=f"phone={model.contact_phone}",
            park_id=int(model.park_id),
            priority="MEDIUM",
            assignee_user_id=model.owner_user_id,
            due_at=(utc_now() + timedelta(days=3)).isoformat(),
            commit=False,
        )

    def _close_follow_todo(self, lead_id: int, *, done: bool) -> None:
        if done:
            self.work_items.complete_by_source(
                source_type="LEAD",
                source_id=str(lead_id),
                item_type=LEAD_FOLLOW_ITEM_TYPE,
                commit=False,
            )
        else:
            self.work_items.cancel_by_source(
                source_type="LEAD",
                source_id=str(lead_id),
                item_type=LEAD_FOLLOW_ITEM_TYPE,
                commit=False,
            )

    def list_leads(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        park_id: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:read"):
            raise AppError("无线索查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        if park_id is not None:
            self._assert_park(int(park_id))
        items = self.leads.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
            park_id=park_id,
            keyword=keyword,
        )
        total = self.leads.count(status=status, park_id=park_id, keyword=keyword)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(x) for x in items],
        }

    def get_lead(self, lead_id: int) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:read"):
            raise AppError("无线索查看权限", code="PERMISSION_DENIED", status_code=403)
        return self._to_dict(self._require(lead_id))

    def create_lead(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:write"):
            raise AppError("无线索维护权限", code="PERMISSION_DENIED", status_code=403)
        park_id = self._assert_park(int(data["park_id"]))
        name = str(data.get("name") or "").strip()
        if not name:
            raise AppError("name 必填", code="VALIDATION_ERROR", status_code=400)
        try:
            phone = normalize_phone(str(data.get("contact_phone") or ""))
            intent = normalize_intent_level(data.get("intent_level"))
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        area = data.get("intent_area")
        intent_area = Decimal(str(area)) if area is not None and area != "" else None
        if intent_area is not None and intent_area < 0:
            raise AppError("intent_area 不得为负", code="VALIDATION_ERROR", status_code=400)

        owner = data.get("owner_user_id")
        owner_user_id = int(owner) if owner is not None else (self.ctx.user_id or None)

        model = self.leads.create(
            park_id=park_id,
            name=name,
            contact_phone=phone,
            contact_name=(str(data["contact_name"]).strip() if data.get("contact_name") else None),
            agent_name=(str(data["agent_name"]).strip() if data.get("agent_name") else None),
            intent_level=intent,
            intent_area=intent_area,
            status="NEW",
            remark=data.get("remark"),
            owner_user_id=owner_user_id,
        )
        self._open_follow_todo(model)
        self.audit.record(
            action="create",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=park_id,
            detail={"name": name[:80]},
        )
        self.session.commit()
        log_business_success(
            logger,
            "线索创建成功",
            ctx=self.ctx,
            module="investment",
            action="create_lead",
            resource_id=model.id,
            park_id=park_id,
        )
        return self._to_dict(model)

    def update_lead(self, lead_id: int, data: dict[str, Any]) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:write"):
            raise AppError("无线索维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(lead_id, for_update=True)
        if model.status in {"WON", "CANCELLED"}:
            raise AppError("终态线索不可修改", code="LEAD_STATUS_INVALID", status_code=400)

        if "name" in data and data["name"] is not None:
            name = str(data["name"]).strip()
            if not name:
                raise AppError("name 不能为空", code="VALIDATION_ERROR", status_code=400)
            model.name = name
        if "contact_phone" in data and data["contact_phone"] is not None:
            try:
                model.contact_phone = normalize_phone(str(data["contact_phone"]))
            except ValueError as exc:
                raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        if "contact_name" in data:
            model.contact_name = (
                str(data["contact_name"]).strip() if data["contact_name"] else None
            )
        if "agent_name" in data:
            model.agent_name = str(data["agent_name"]).strip() if data["agent_name"] else None
        if "intent_level" in data:
            try:
                model.intent_level = normalize_intent_level(data.get("intent_level"))
            except ValueError as exc:
                raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        if "intent_area" in data:
            raw = data.get("intent_area")
            model.intent_area = Decimal(str(raw)) if raw not in (None, "") else None
        if "remark" in data:
            model.remark = data.get("remark")
        if "owner_user_id" in data:
            model.owner_user_id = (
                int(data["owner_user_id"]) if data["owner_user_id"] is not None else None
            )
        if "status" in data and data["status"]:
            try:
                model.status = assert_status_transition(model.status, str(data["status"]))
            except ValueError as exc:
                raise AppError(str(exc), code="LEAD_STATUS_INVALID", status_code=400) from exc

        # 跟进中自动打开待办
        if model.status == "FOLLOWING":
            self._open_follow_todo(model)

        self.leads.save(model)
        self.audit.record(
            action="update",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"fields": sorted(data.keys())},
        )
        self.session.commit()
        return self._to_dict(model)

    def mark_lost(self, lead_id: int, *, reason: Optional[str] = None) -> dict[str, Any]:
        if not self.ctx.has_permission("lead:write"):
            raise AppError("无线索维护权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require(lead_id, for_update=True)
        try:
            model.status = assert_status_transition(model.status, "LOST")
        except ValueError as exc:
            raise AppError(str(exc), code="LEAD_STATUS_INVALID", status_code=400) from exc
        model.lost_reason = (reason or "").strip() or None
        self.leads.save(model)
        self._close_follow_todo(lead_id, done=False)
        self.audit.record(
            action="lose",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"reason": (model.lost_reason or "")[:80]},
        )
        self.session.commit()
        return self._to_dict(model)

    def convert_lead(self, lead_id: int, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """功能说明：线索转主体，可选创建合同草稿（不自动激活）。"""

        if not self.ctx.has_permission("lead:convert"):
            raise AppError("无线索转化权限", code="PERMISSION_DENIED", status_code=403)
        if not self.ctx.has_permission("party:write"):
            raise AppError("转化需主体写权限", code="PERMISSION_DENIED", status_code=403)

        data = data or {}
        model = self._require(lead_id, for_update=True)
        if model.status not in CONVERTIBLE:
            raise AppError("仅跟进中线索可转化", code="LEAD_STATUS_INVALID", status_code=400)

        self._assert_park(int(model.park_id))

        # 创建主体（带初始园区关系）
        party = self.parties.create_party(
            {
                "name": model.name,
                "party_type": str(data.get("party_type") or "ORGANIZATION"),
                "contact_name": model.contact_name or model.name,
                "contact_phone": model.contact_phone,
                "remark": f"from_lead:{model.id}",
                "initial_park_relation": {
                    "park_id": int(model.park_id),
                    "role_code": "LESSEE",
                },
            }
        )
        # create_party commits — 重新绑定 session 状态，继续同会话操作
        # PartyService commits internally; re-load lead and continue carefully.
        model = self._require(lead_id, for_update=True)
        model.party_id = int(party["id"])

        lease_dict: Optional[dict[str, Any]] = None
        unit_ids = data.get("unit_ids") or []
        start_raw = data.get("start_date")
        end_raw = data.get("end_date")

        if unit_ids or start_raw or end_raw:
            if not self.ctx.has_permission("lease:write"):
                raise AppError("转化建合同需租赁写权限", code="PERMISSION_DENIED", status_code=403)
            if not start_raw or not end_raw:
                raise AppError(
                    "创建合同草稿须同时提供 start_date 与 end_date",
                    code="VALIDATION_ERROR",
                    status_code=400,
                )
            units = [
                {
                    "unit_id": int(uid),
                    "occupied_area": str(data.get("occupied_area") or "0"),
                    "unit_rent_price": str(data.get("unit_rent_price") or "0"),
                }
                for uid in unit_ids
            ]
            lease_dict = self.leases.create_contract(
                {
                    "park_id": int(model.park_id),
                    "party_id": int(party["id"]),
                    "start_date": start_raw,
                    "end_date": end_raw,
                    "deposit_amount": data.get("deposit_amount") or "0",
                    "units": units,
                    "remark": f"from_lead:{model.id}",
                }
            )
            # create_contract also commits
            model = self._require(lead_id, for_update=True)
            model.lease_id = int(lease_dict["id"])

        try:
            model.status = assert_status_transition(model.status, "WON")
        except ValueError as exc:
            raise AppError(str(exc), code="LEAD_STATUS_INVALID", status_code=400) from exc
        model.converted_at = utc_now()
        self.leads.save(model)
        self._close_follow_todo(lead_id, done=True)
        self.audit.record(
            action="convert",
            resource_type="LEAD",
            resource_id=model.id,
            park_id=model.park_id,
            detail={
                "party_id": model.party_id,
                "lease_id": model.lease_id,
            },
        )
        self.session.commit()

        log_business_success(
            logger,
            "线索转化成功",
            ctx=self.ctx,
            module="investment",
            action="convert_lead",
            resource_id=model.id,
            park_id=model.park_id,
        )
        return {
            "lead": self._to_dict(model),
            "party": party,
            "lease": lease_dict,
        }
