"""Governed Lease V2 submit, approval, document and activation use cases."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.lease.application.occupancy_service import OccupancyService
from app.modules.lease.domain.entities import (
    LeaseChangeOrderEntity,
    LeaseChargeItemEntity,
    LeaseContractDocumentEntity,
    LeaseContractUnitEntity,
    LeaseContractVersionEntity,
    LeaseExitItemEntity,
    LeaseExitSettlementEntity,
)
from app.modules.lease.domain.errors import LeaseDomainError
from app.modules.lease.domain.changes import (
    assert_base_version,
    assert_change_status_transition,
    validate_change_proposal,
)
from app.modules.lease.domain.pricing import generate_performance_schedule, schedule_checksum
from app.modules.lease.domain.rules import assert_v2_status_transition
from app.modules.lease.domain.versioning import (
    assert_expected_version,
    canonical_value,
    canonical_snapshot,
    snapshot_checksum,
)
from app.modules.lease.domain.settlement import (
    assert_exit_status_transition,
    assert_financial_clearance,
    calculate_exit_totals,
)
from app.modules.lease.infrastructure.approval_adapter import WorkflowApprovalCommandAdapter
from app.modules.lease.infrastructure.collaboration_adapters import (
    CrmUnitLockReadAdapter,
    CurrentUnitReferenceAdapter,
    LeaseWorkItemAdapter,
    ScopedAttachmentEvidenceAdapter,
    ScopedParkReferenceAdapter,
    ScopedPartyEligibilityAdapter,
)
from app.modules.lease.infrastructure.lease_repository import (
    LeaseChargeItemRepository,
    LeaseChangeOrderRepository,
    LeaseContractDocumentRepository,
    LeaseContractRepository,
    LeaseContractUnitRepository,
    LeaseContractVersionRepository,
    LeaseExitItemRepository,
    LeaseExitSettlementRepository,
    LeasePerformanceScheduleRepository,
    lock_current_units,
)
from app.modules.lease.infrastructure.mappers import (
    LeaseChangeOrderMapper,
    LeaseChargeItemMapper,
    LeaseContractDocumentMapper,
    LeaseContractUnitMapper,
    LeaseContractVersionMapper,
    LeaseExitItemMapper,
    LeaseExitSettlementMapper,
    LeasePerformanceScheduleMapper,
)
from app.modules.lease.infrastructure.signature_adapter import (
    FailClosedSignatureAdapter,
    LocalSandboxSignatureAdapter,
)
from app.modules.lease.infrastructure.billing_outstanding_adapter import (
    SqlAlchemyBillingOutstandingAdapter,
)
from app.shared.tenant_context import TenantContext


class ContractLifecycleService:
    """Coordinates V2 governance in one caller-owned database transaction."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.contracts = LeaseContractRepository(session, ctx)
        self.units = LeaseContractUnitRepository(session, ctx)
        self.charges = LeaseChargeItemRepository(session, ctx)
        self.changes = LeaseChangeOrderRepository(session, ctx)
        self.schedules = LeasePerformanceScheduleRepository(session, ctx)
        self.versions = LeaseContractVersionRepository(session, ctx)
        self.documents = LeaseContractDocumentRepository(session, ctx)
        self.exits = LeaseExitSettlementRepository(session, ctx)
        self.exit_items = LeaseExitItemRepository(session, ctx)
        self.billing_outstanding = SqlAlchemyBillingOutstandingAdapter(session, ctx)
        self.approvals = WorkflowApprovalCommandAdapter(session, ctx)
        self.attachments = ScopedAttachmentEvidenceAdapter(session, ctx)
        self.parties = ScopedPartyEligibilityAdapter(session, ctx)
        self.parks = ScopedParkReferenceAdapter(session, ctx)
        self.current_units = CurrentUnitReferenceAdapter(session, ctx)
        self.crm_unit_locks = CrmUnitLockReadAdapter(session, ctx)
        self.occupancy = OccupancyService(session, ctx)
        self.work_items = LeaseWorkItemAdapter(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def create_draft(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create header, units, charges and a validated schedule in one transaction."""

        self._permission("lease:write")
        from app.modules.lease.application.lease_service import LeaseService

        payload = dict(data)
        charges = payload.pop("charges", None)
        if not charges:
            raise AppError("合同草稿须配置费用", code="LEASE_CHARGES_REQUIRED", status_code=400)
        try:
            contract = LeaseService(self.session, self.ctx).create_contract(payload, commit=False)
            preview = self.replace_draft_charges(
                int(contract["id"]),
                expected_version=int(contract["lock_version"]),
                charges=charges,
                commit=False,
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        result = LeaseService(self.session, self.ctx).get_contract(int(contract["id"]))
        result["schedule_preview"] = preview
        return result

    def update_draft(
        self, contract_id: int, *, expected_version: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Replace draft facts and optional charges atomically under optimistic locking."""

        self._permission("lease:write")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        if model.status != "DRAFT":
            raise AppError(
                "已生效合同须走变更单",
                code="LEASE_CHANGE_ORDER_REQUIRED",
                status_code=409,
            )
        from app.modules.lease.application.lease_service import LeaseService

        payload = dict(data)
        charges = payload.pop("charges", None)
        try:
            updated = LeaseService(self.session, self.ctx).update_contract(
                contract_id, payload, commit=False
            )
            preview = None
            if charges is not None:
                preview = self.replace_draft_charges(
                    contract_id,
                    expected_version=int(updated["lock_version"]),
                    charges=charges,
                    commit=False,
                )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        result = LeaseService(self.session, self.ctx).get_contract(contract_id)
        if preview is not None:
            result["schedule_preview"] = preview
        return result

    def summary(
        self, *, park_id: Optional[int] = None, as_of: Optional[date] = None
    ) -> dict[str, Any]:
        self._permission("lease:read")
        day = as_of or date.today()
        current_statuses = {"ACTIVE", "EXPIRING", "EXIT_PENDING"}
        unresolved = self.exits.unresolved_clearance_summary(park_id=park_id)
        return {
            "as_of": day.isoformat(),
            "park_id": park_id,
            "metrics": {
                "current_contracts": self.contracts.count_statuses(
                    current_statuses, park_id=park_id
                ),
                "current_deposit_amount": str(
                    self.contracts.sum_deposit(current_statuses, park_id=park_id)
                ),
                "expiring_within_90_days": self.contracts.count_expiring(
                    within_days=90, as_of=day, park_id=park_id
                ),
                "pending_approval": self.contracts.count_statuses(
                    {"PENDING_APPROVAL"}, park_id=park_id
                ),
                "due_changes": self.changes.count_due_approved(day, park_id=park_id),
                "exit_pending": self.contracts.count_statuses({"EXIT_PENDING"}, park_id=park_id),
                "unresolved_clearance": unresolved["count"],
                "unresolved_clearance_amount": str(unresolved["amount"]),
            },
            "amount_semantics": {
                "current_deposit_amount": "stored contract deposit; no money movement",
                "unresolved_clearance_amount": "external evidence required; no money movement",
            },
        }

    def selectors(
        self, *, park_id: Optional[int] = None, keyword: Optional[str] = None
    ) -> dict[str, Any]:
        self._permission("lease:read")
        return {
            "parks": self.parks.options(keyword=keyword),
            "parties": self.parties.options(park_id=park_id, keyword=keyword),
            "units": self.current_units.options(park_id=park_id, keyword=keyword),
            "park_id": park_id,
        }

    def party_profile(self, party_id: int) -> dict[str, Any]:
        self._permission("lease:read")
        party = self.parties.get_by_id(int(party_id))
        if party is None:
            raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        contracts = list(self.contracts.list(offset=0, limit=200, party_id=int(party_id)))
        current_statuses = {"ACTIVE", "EXPIRING", "EXIT_PENDING"}
        current: list[dict[str, Any]] = []
        history: list[dict[str, Any]] = []
        outstanding_total = Decimal("0")
        billing_as_of: Optional[datetime] = None
        billing_sources: set[str] = set()
        for model in contracts:
            billing = self.billing_outstanding.for_contract(int(model.id))
            outstanding_total += billing.amount
            billing_as_of = max(billing_as_of, billing.as_of) if billing_as_of else billing.as_of
            billing_sources.add(billing.source)
            row = {
                "id": int(model.id),
                "park_id": int(model.park_id),
                "contract_no": model.contract_no,
                "contract_type": model.contract_type,
                "status": model.status,
                "start_date": model.start_date.isoformat(),
                "end_date": model.end_date.isoformat(),
                "current_version_no": int(model.current_version_no),
                "lock_version": int(model.lock_version),
                "outstanding_amount": str(billing.amount),
                "outstanding_source": billing.source,
                "outstanding_as_of": billing.as_of.isoformat(),
            }
            (current if model.status in current_statuses else history).append(row)
        return {
            "party": {
                "id": int(party.id),
                "name": party.name,
                "status": party.status,
                "risk_status": party.risk_status,
            },
            "current_contracts": current,
            "history_contracts": history,
            "billing_summary": {
                "outstanding_amount": str(outstanding_total),
                "sources": sorted(billing_sources),
                "as_of": billing_as_of.isoformat() if billing_as_of else None,
                "financial_effect": "NONE",
            },
        }

    @staticmethod
    def _date(value: Any, field: str) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError) as exc:
            raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400) from exc

    @staticmethod
    def _domain_call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except LeaseDomainError as exc:
            status = 409 if exc.code.endswith("CONFLICT") or exc.code.endswith("REQUIRED") else 400
            raise AppError(str(exc), code=exc.code, status_code=status) from exc

    def _permission(self, *permissions: str) -> None:
        if not all(self.ctx.has_permission(code) for code in permissions):
            raise AppError("权限不足", code="PERMISSION_DENIED", status_code=403)

    def _contract(self, contract_id: int, *, for_update: bool = False):
        model = (
            self.contracts.get_for_update(contract_id)
            if for_update
            else self.contracts.get_by_id(contract_id)
        )
        if model is None:
            raise AppError("合同不存在", code="LEASE_NOT_FOUND", status_code=404)
        return model

    def _expected(self, model, expected_version: Optional[int]) -> None:
        self._domain_call(assert_expected_version, int(model.lock_version), expected_version)

    def _unit_dicts(self, contract_id: int) -> list[dict[str, Any]]:
        return [
            {
                "id": row.id,
                "unit_id": row.unit_id,
                "occupied_area": Decimal(str(row.occupied_area or 0)),
                "unit_rent_price": Decimal(str(row.unit_rent_price or 0)),
            }
            for row in self.units.list_for_contract(contract_id)
        ]

    def _charge_dicts(self, contract_id: int) -> list[dict[str, Any]]:
        return [
            asdict(LeaseChargeItemMapper.to_entity(row))
            for row in self.charges.list_for_contract(contract_id)
        ]

    def _generate_schedule(self, model, *, version_no: int):
        charge_rows = self.charges.list_for_contract(int(model.id))
        charge_values = [asdict(LeaseChargeItemMapper.to_entity(row)) for row in charge_rows]
        rules: list[dict[str, Any]] = []
        for charge in charge_rows:
            for raw in charge.rules_json or []:
                rule = dict(raw)
                rule.setdefault("charge_code", charge.charge_code)
                if rule.get("type") == "INCREASE":
                    rule["rule_type"] = "ESCALATION"
                rules.append(rule)
        schedule = self._domain_call(
            generate_performance_schedule,
            tenant_id=self.ctx.tenant_id,
            contract_id=int(model.id),
            contract_version_no=version_no,
            contract_start=model.start_date,
            contract_end=model.end_date,
            charges=charge_values,
            units=self._unit_dicts(int(model.id)),
            rules=rules,
            contract_currency=model.currency,
        )
        charge_ids = {row.charge_code: row.id for row in charge_rows}
        return [
            row.__class__(**{**asdict(row), "charge_item_id": charge_ids.get(row.charge_code)})
            for row in schedule
        ]

    def _snapshot(self, model, schedule) -> dict[str, Any]:
        return canonical_snapshot(
            {
                "contract": {
                    "id": model.id,
                    "park_id": model.park_id,
                    "party_id": model.party_id,
                    "contract_no": model.contract_no,
                    "contract_type": model.contract_type,
                    "currency": model.currency,
                    "status": model.status,
                    "start_date": model.start_date,
                    "end_date": model.end_date,
                    "deposit_amount": Decimal(str(model.deposit_amount or 0)),
                    "remark": model.remark,
                },
                "units": self._unit_dicts(int(model.id)),
                "charges": self._charge_dicts(int(model.id)),
                "schedules": [asdict(row) for row in schedule],
            }
        )

    def _current_snapshot(self, model) -> dict[str, Any]:
        schedules = [
            LeasePerformanceScheduleMapper.to_entity(row)
            for row in self.schedules.list_for_contract(
                int(model.id), version_no=int(model.current_version_no or 0)
            )
        ]
        return self._snapshot(model, schedules)

    @staticmethod
    def _schedule_dict(row) -> dict[str, Any]:
        return {
            "schedule_key": row.schedule_key,
            "charge_code": row.charge_code,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "due_date": row.due_date.isoformat(),
            "currency": row.currency,
            "area": str(row.area),
            "unit_price": str(row.unit_price) if row.unit_price is not None else None,
            "net_amount": str(row.net_amount),
            "tax_amount": str(row.tax_amount),
            "gross_amount": str(row.gross_amount),
            "rule_refs": list(row.rule_refs),
        }

    def _exit_dict(self, settlement) -> Optional[dict[str, Any]]:
        if settlement is None:
            return None
        return {
            "id": settlement.id,
            "change_order_id": settlement.change_order_id,
            "settlement_no": settlement.settlement_no,
            "contract_version_no": settlement.contract_version_no,
            "status": settlement.status,
            "lock_version": settlement.lock_version,
            "handover_date": (
                settlement.handover_date.isoformat() if settlement.handover_date else None
            ),
            "inspection_summary": settlement.inspection_summary,
            "meter_readings": settlement.meter_readings_json or [],
            "held_deposit_amount": str(settlement.held_deposit_amount),
            "outstanding_amount": str(settlement.outstanding_amount),
            "outstanding_source": settlement.outstanding_source,
            "outstanding_as_of": settlement.outstanding_as_of.isoformat(),
            "receivable_total": str(settlement.receivable_total),
            "deduction_total": str(settlement.deduction_total),
            "refund_adjustment_total": str(settlement.refund_adjustment_total),
            "net_due_from_party": str(settlement.net_due_from_party),
            "net_due_to_party": str(settlement.net_due_to_party),
            "checksum": settlement.checksum,
            "financial_clearance_status": settlement.financial_clearance_status,
            "clearance_reference": settlement.clearance_reference,
            "approval_id": settlement.approval_id,
            "items": [
                {
                    "id": item.id,
                    "item_type": item.item_type,
                    "description": item.description,
                    "amount": str(item.amount),
                    "approved": item.approved,
                    "evidence_attachment_id": item.evidence_attachment_id,
                    "sort_order": item.sort_order,
                }
                for item in self.exit_items.list_for_settlement(int(settlement.id))
            ],
            "financial_effect": "NONE",
        }

    def _latest_exit_dict(self, contract_id: int) -> Optional[dict[str, Any]]:
        rows = self.exits.list_for_contract(contract_id)
        return self._exit_dict(rows[0]) if rows else None

    def preview_schedule(
        self,
        contract_id: int,
        *,
        expected_version: int,
        charges: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        self._permission("lease:read")
        model = self._contract(contract_id)
        self._expected(model, expected_version)
        if charges is not None:
            entities: list[LeaseChargeItemEntity] = []
            for index, raw in enumerate(charges):
                entities.append(
                    LeaseChargeItemEntity(
                        tenant_id=self.ctx.tenant_id,
                        contract_id=int(model.id),
                        charge_code=str(raw.get("charge_code") or ""),
                        charge_type=str(raw.get("charge_type") or ""),
                        calculation_method=str(raw.get("calculation_method") or ""),
                        billing_cycle=str(raw.get("billing_cycle") or ""),
                        currency=str(raw.get("currency") or model.currency),
                        start_date=self._date(raw.get("start_date"), "start_date"),
                        end_date=self._date(raw.get("end_date"), "end_date"),
                        due_day=int(raw.get("due_day") or 1),
                        amount=(
                            Decimal(str(raw["amount"])) if raw.get("amount") is not None else None
                        ),
                        unit_price=(
                            Decimal(str(raw["unit_price"]))
                            if raw.get("unit_price") is not None
                            else None
                        ),
                        tax_rate=Decimal(str(raw.get("tax_rate") or 0)),
                        sort_order=int(raw.get("sort_order", index)),
                        rule_config={"rules": raw.get("rules") or []},
                    )
                )
            charge_values = [asdict(entity) for entity in entities]
            rules = [
                {**dict(rule), "charge_code": entity.charge_code}
                for entity in entities
                for rule in entity.rule_config.get("rules", [])
            ]
            schedule = self._domain_call(
                generate_performance_schedule,
                tenant_id=self.ctx.tenant_id,
                contract_id=int(model.id),
                contract_version_no=int(model.current_version_no or 0),
                contract_start=model.start_date,
                contract_end=model.end_date,
                charges=charge_values,
                units=self._unit_dicts(int(model.id)),
                rules=rules,
                contract_currency=model.currency,
            )
        else:
            schedule = self._generate_schedule(model, version_no=int(model.current_version_no or 0))
        return {
            "contract_id": model.id,
            "lock_version": model.lock_version,
            "current_version_no": model.current_version_no,
            "row_count": len(schedule),
            "checksum": schedule_checksum(schedule),
            "rows": [self._schedule_dict(row) for row in schedule],
            "billing_effect": "NONE",
        }

    def replace_draft_charges(
        self,
        contract_id: int,
        *,
        expected_version: int,
        charges: list[dict[str, Any]],
        commit: bool = True,
    ) -> dict[str, Any]:
        self._permission("lease:write")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        if model.status != "DRAFT":
            raise AppError(
                "已生效合同须走变更单",
                code="LEASE_CHANGE_ORDER_REQUIRED",
                status_code=409,
            )
        entities: list[LeaseChargeItemEntity] = []
        for index, raw in enumerate(charges):
            entities.append(
                LeaseChargeItemEntity(
                    tenant_id=self.ctx.tenant_id,
                    contract_id=int(model.id),
                    charge_code=str(raw.get("charge_code") or "").upper(),
                    charge_type=str(raw.get("charge_type") or "").upper(),
                    calculation_method=str(raw.get("calculation_method") or "").upper(),
                    billing_cycle=str(raw.get("billing_cycle") or "").upper(),
                    currency=str(raw.get("currency") or model.currency).upper(),
                    start_date=self._date(raw.get("start_date"), "start_date"),
                    end_date=self._date(raw.get("end_date"), "end_date"),
                    due_day=int(raw.get("due_day") or 1),
                    amount=Decimal(str(raw["amount"])) if raw.get("amount") is not None else None,
                    unit_price=(
                        Decimal(str(raw["unit_price"]))
                        if raw.get("unit_price") is not None
                        else None
                    ),
                    tax_rate=Decimal(str(raw.get("tax_rate") or 0)),
                    sort_order=int(raw.get("sort_order", index)),
                    rule_config={"rules": raw.get("rules") or []},
                )
            )
        models = [LeaseChargeItemMapper.new_model(entity) for entity in entities]
        try:
            self.charges.replace_for_contract(int(model.id), models)
            schedule = self._generate_schedule(model, version_no=0)
            model.lock_version += 1
            self.contracts.save(model)
            self.audit.record(
                action="replace_charges",
                resource_type="LEASE_CONTRACT",
                resource_id=model.id,
                park_id=model.park_id,
                detail={"charge_count": len(models), "schedule_count": len(schedule)},
            )
            if commit:
                self.session.commit()
            else:
                self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("费用项冲突", code="LEASE_CHARGE_INVALID", status_code=409) from exc
        return {
            "contract_id": model.id,
            "lock_version": model.lock_version,
            "current_version_no": model.current_version_no,
            "row_count": len(schedule),
            "checksum": schedule_checksum(schedule),
            "rows": [self._schedule_dict(row) for row in schedule],
            "billing_effect": "NONE",
        }

    def submit(self, contract_id: int, *, expected_version: int, remark: Optional[str]) -> dict:
        self._permission("lease:write", "approval:write")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        self._domain_call(assert_v2_status_transition, model.status, "PENDING_APPROVAL")
        if not self.units.list_for_contract(contract_id):
            raise AppError("提交前须配置单元", code="LEASE_UNITS_REQUIRED", status_code=400)
        schedule = self._generate_schedule(model, version_no=0)
        if not schedule:
            raise AppError("提交前须配置费用", code="LEASE_CHARGES_REQUIRED", status_code=400)
        revision = int(model.lock_version) + 1
        approval = self.approvals.submit(
            park_id=int(model.park_id),
            biz_type="LEASE_CONTRACT_VERSION",
            biz_id=f"{model.id}:r{revision}",
            title=f"合同提交审批 {model.contract_no}",
            remark=remark,
        )
        model.status = "PENDING_APPROVAL"
        model.approval_status = "PENDING"
        model.lock_version = revision
        self.contracts.save(model)
        self.work_items.ensure_from_source(
            source_type="LEASE_APPROVAL",
            source_id=str(approval.id),
            item_type="LEASE_CONTRACT_APPROVAL",
            title=f"待审批合同 {model.contract_no}",
            park_id=int(model.park_id),
            priority="HIGH",
            commit=False,
        )
        self.audit.record(
            action="submit_v2",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"approval_id": approval.id, "revision": revision},
        )
        self.session.commit()
        result = self.detail(contract_id)
        result["pending_approval"] = {
            "id": approval.id,
            "biz_type": approval.biz_type,
            "status": approval.status,
        }
        return result

    def decide(
        self,
        contract_id: int,
        *,
        approval_id: int,
        approve: bool,
        expected_version: int,
        remark: Optional[str],
        override_reason: Optional[str] = None,
    ) -> dict:
        self._permission("approval:decide", "lease:approve")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        if model.status != "PENDING_APPROVAL":
            raise AppError("合同非待审批", code="LEASE_STATUS_INVALID", status_code=409)
        approval = self.approvals.get(approval_id, for_update=True)
        if approval.biz_type != "LEASE_CONTRACT_VERSION" or not approval.biz_id.startswith(
            f"{model.id}:"
        ):
            raise AppError("审批与合同不匹配", code="APPROVAL_NOT_FOUND", status_code=404)
        self.approvals.decide(
            approval_id,
            approve=approve,
            remark=remark,
            override_reason=override_reason,
        )
        model.status = "PENDING_ACTIVE" if approve else "DRAFT"
        model.approval_status = "APPROVED" if approve else "REJECTED"
        model.lock_version += 1
        self.contracts.save(model)
        self.work_items.complete_by_source(
            source_type="LEASE_APPROVAL",
            source_id=str(approval_id),
            item_type="LEASE_CONTRACT_APPROVAL",
            commit=False,
        )
        self.audit.record(
            action="approve_v2" if approve else "reject_v2",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"approval_id": approval_id, "override": bool(override_reason)},
        )
        self.session.commit()
        return self.detail(contract_id)

    def withdraw(
        self,
        contract_id: int,
        *,
        approval_id: int,
        expected_version: int,
        remark: Optional[str],
    ) -> dict:
        self._permission("lease:write", "approval:write")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        if model.status != "PENDING_APPROVAL":
            raise AppError("合同非待审批", code="LEASE_STATUS_INVALID", status_code=409)
        approval = self.approvals.get(approval_id, for_update=True)
        if not approval.biz_id.startswith(f"{model.id}:"):
            raise AppError("审批与合同不匹配", code="APPROVAL_NOT_FOUND", status_code=404)
        self.approvals.withdraw(approval_id, remark=remark)
        model.status = "DRAFT"
        model.approval_status = "WITHDRAWN"
        model.lock_version += 1
        self.contracts.save(model)
        self.work_items.complete_by_source(
            source_type="LEASE_APPROVAL",
            source_id=str(approval_id),
            item_type="LEASE_CONTRACT_APPROVAL",
            commit=False,
        )
        self.audit.record(
            action="withdraw_v2",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"approval_id": approval_id},
        )
        self.session.commit()
        return self.detail(contract_id)

    def cancel_draft(self, contract_id: int, *, expected_version: int) -> dict[str, Any]:
        """Cancel only a pre-submission draft; activated contracts require exit governance."""

        self._permission("lease:write")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        self._domain_call(assert_v2_status_transition, model.status, "CANCELLED")
        if model.status != "DRAFT":
            raise AppError(
                "待审批合同须先撤回，已生效合同须走退租结算",
                code="LEASE_DOMAIN_COMMAND_REQUIRED",
                status_code=409,
            )
        model.status = "CANCELLED"
        model.lock_version += 1
        self.contracts.save(model)
        self.work_items.cancel_by_source(
            source_type="LEASE_APPROVAL",
            source_id=str(model.id),
            item_type="LEASE_CONTRACT_APPROVAL",
            commit=False,
        )
        self.audit.record(
            action="cancel_draft",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={"expected_version": expected_version},
        )
        self.session.commit()
        return self.detail(contract_id)

    def add_document(
        self,
        contract_id: int,
        *,
        expected_version: int,
        attachment_id: int,
        document_type: str,
        checksum: str,
        is_main: bool,
        exit_settlement_id: Optional[int] = None,
    ) -> dict:
        self._permission("lease:document")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        attachment = self.attachments.get(int(attachment_id))
        settlement = None
        if exit_settlement_id is not None:
            settlement = self.exits.get(int(exit_settlement_id))
            if settlement is None or int(settlement.contract_id) != int(model.id):
                raise AppError("退租结算不存在", code="LEASE_EXIT_NOT_FOUND", status_code=404)
        if (
            attachment is None
            or attachment.status != "ACTIVE"
            or (attachment.park_id is not None and int(attachment.park_id) != int(model.park_id))
            or attachment.biz_type
            != ("LEASE_EXIT_SETTLEMENT" if settlement is not None else "LEASE_CONTRACT")
            or attachment.biz_id
            != (str(settlement.id) if settlement is not None else str(model.id))
        ):
            raise AppError("附件不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
        checksum = (checksum or "").strip().lower()
        if len(checksum) != 64 or any(ch not in "0123456789abcdef" for ch in checksum):
            raise AppError("文档校验和无效", code="LEASE_DOCUMENT_INVALID", status_code=400)
        existing = self.documents.list_for_contract(contract_id)
        version = (
            max(
                (row.document_version for row in existing if row.document_type == document_type),
                default=0,
            )
            + 1
        )
        entity = LeaseContractDocumentEntity(
            tenant_id=self.ctx.tenant_id,
            contract_id=contract_id,
            attachment_id=attachment_id,
            document_type=document_type,
            document_version=version,
            status="DRAFT",
            checksum=checksum,
            is_main=is_main,
            contract_version_no=model.current_version_no or None,
            exit_settlement_id=settlement.id if settlement is not None else None,
            created_by=self.ctx.user_id or None,
        )
        document = self.documents.add(
            LeaseContractDocumentMapper.new_model(entity, park_id=int(model.park_id))
        )
        model.lock_version += 1
        self.contracts.save(model)
        self.work_items.ensure_from_source(
            source_type="LEASE_DOCUMENT",
            source_id=str(document.id),
            item_type="LEASE_DOCUMENT_REVIEW",
            title=f"审核合同文档 {model.contract_no}",
            description=f"{document.document_type} V{document.document_version}",
            park_id=int(model.park_id),
            priority="HIGH" if document.is_main else "MEDIUM",
            commit=False,
        )
        self.audit.record(
            action="add_document",
            resource_type="LEASE_CONTRACT_DOCUMENT",
            resource_id=document.id,
            park_id=model.park_id,
            detail={"document_type": document_type, "checksum_prefix": checksum[:12]},
        )
        self.session.commit()
        return self.detail(contract_id)

    def advance_document(
        self,
        contract_id: int,
        document_id: int,
        *,
        expected_version: int,
        target_status: str,
    ) -> dict:
        self._permission("lease:document")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        source = next(
            (row for row in self.documents.list_for_contract(contract_id) if row.id == document_id),
            None,
        )
        if source is None:
            raise AppError("合同文档不存在", code="LEASE_DOCUMENT_NOT_FOUND", status_code=404)
        normalized = target_status.upper()
        if normalized not in {"APPROVED", "SIGNED", "VOID"}:
            raise AppError("文档状态无效", code="LEASE_DOCUMENT_INVALID", status_code=400)
        provider = source.signature_provider
        signature_ref = source.signature_ref
        live_verified = source.live_verified
        signed_at = source.signed_at
        persisted_status = normalized
        if normalized == "SIGNED":
            adapter = (
                LocalSandboxSignatureAdapter()
                if get_settings().app_env.lower() in {"local", "test", "development"}
                else FailClosedSignatureAdapter()
            )
            result = adapter.sign(document_id=int(source.id), checksum=source.checksum)
            provider = result.provider
            signature_ref = result.signature_ref
            live_verified = result.live_verified
            signed_at = utc_now()
            if not live_verified:
                persisted_status = "SANDBOX_COMPLETED"
        version = (
            max(
                row.document_version
                for row in self.documents.list_for_contract(contract_id)
                if row.document_type == source.document_type
            )
            + 1
        )
        entity = LeaseContractDocumentEntity(
            tenant_id=self.ctx.tenant_id,
            contract_id=contract_id,
            attachment_id=source.attachment_id,
            document_type=source.document_type,
            document_version=version,
            status=persisted_status,
            checksum=source.checksum,
            is_main=source.is_main,
            contract_version_no=source.contract_version_no,
            change_order_id=source.change_order_id,
            exit_settlement_id=source.exit_settlement_id,
            signature_provider=provider,
            signature_ref=signature_ref,
            signed_at=signed_at,
            live_verified=live_verified,
            created_by=self.ctx.user_id or None,
        )
        document = self.documents.add(
            LeaseContractDocumentMapper.new_model(entity, park_id=int(model.park_id))
        )
        model.lock_version += 1
        self.contracts.save(model)
        if normalized == "APPROVED":
            self.work_items.complete_by_source(
                source_type="LEASE_DOCUMENT",
                source_id=str(source.id),
                item_type="LEASE_DOCUMENT_REVIEW",
                commit=False,
            )
            self.work_items.ensure_from_source(
                source_type="LEASE_DOCUMENT",
                source_id=str(document.id),
                item_type="LEASE_SIGNATURE_WAIT",
                title=f"等待合同文档签署 {model.contract_no}",
                description=f"{document.document_type} V{document.document_version}",
                park_id=int(model.park_id),
                priority="MEDIUM",
                commit=False,
            )
        elif persisted_status == "SIGNED":
            self.work_items.complete_by_source(
                source_type="LEASE_DOCUMENT",
                source_id=str(source.id),
                item_type="LEASE_SIGNATURE_WAIT",
                commit=False,
            )
        elif normalized == "VOID":
            for item_type in ("LEASE_DOCUMENT_REVIEW", "LEASE_SIGNATURE_WAIT"):
                self.work_items.cancel_by_source(
                    source_type="LEASE_DOCUMENT",
                    source_id=str(source.id),
                    item_type=item_type,
                    commit=False,
                )
        self.audit.record(
            action=f"document_{persisted_status.lower()}",
            resource_type="LEASE_CONTRACT_DOCUMENT",
            resource_id=document.id,
            park_id=model.park_id,
            detail={
                "document_type": source.document_type,
                "checksum_prefix": source.checksum[:12],
                "provider": provider,
                "live_verified": live_verified,
                "requested_status": normalized,
                "persisted_status": persisted_status,
            },
        )
        self.session.commit()
        return self.detail(contract_id)

    def activate(self, contract_id: int, *, expected_version: int) -> dict:
        self._permission("lease:activate")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        if model.status != "PENDING_ACTIVE":
            raise AppError(
                "合同必须先完成领域审批",
                code="LEASE_APPROVAL_REQUIRED",
                status_code=409,
            )
        self._domain_call(assert_v2_status_transition, model.status, "ACTIVE")
        documents = self.documents.list_for_contract(contract_id)
        current_main = [
            row for row in documents if row.is_main and row.status in {"APPROVED", "SIGNED"}
        ]
        if not current_main:
            raise AppError("缺少已批准主合同文档", code="LEASE_DOCUMENT_REQUIRED", status_code=409)
        party = self.parties.get_by_id(int(model.party_id))
        if party is None or party.status == "ARCHIVED" or party.risk_status == "BLACKLISTED":
            raise AppError("签约主体不可激活", code="PARTY_STATUS_INVALID", status_code=409)
        lines = self.units.list_for_contract(contract_id)
        unit_models = lock_current_units(self.session, [line.unit_id for line in lines])
        if len(unit_models) != len(lines):
            raise AppError("单元版本已变化", code="OCCUPANCY_CONFLICT", status_code=409)
        now = utc_now()
        consumed_locks: list[Any] = []
        for unit in unit_models:
            active_lock = self.crm_unit_locks.active_for_unit(int(unit.id), for_update=True)
            if active_lock is not None and active_lock.expires_at <= now:
                active_lock.status = "EXPIRED"
                active_lock.released_at = now
                active_lock.lock_version += 1
                self.session.add(active_lock)
                active_lock = None
            if active_lock is not None:
                if int(active_lock.lease_id or 0) != int(model.id):
                    raise AppError(
                        "单元存在不属于当前合同的有效招商锁",
                        code="UNIT_ALREADY_LOCKED",
                        status_code=409,
                    )
                consumed_locks.append(active_lock)
        area_by_id = {int(line.unit_id): Decimal(str(line.occupied_area or 0)) for line in lines}
        self.occupancy.assert_can_activate_lines(
            contract_id=contract_id,
            lines=[(unit, area_by_id[int(unit.id)]) for unit in unit_models],
        )
        schedule = self._generate_schedule(model, version_no=1)
        model.status = "ACTIVE"
        model.current_version_no = 1
        model.effective_at = utc_now()
        model.lock_version += 1
        snapshot = self._snapshot(model, schedule)
        version = LeaseContractVersionEntity(
            tenant_id=self.ctx.tenant_id,
            contract_id=int(model.id),
            version_no=1,
            schema_version=1,
            snapshot=snapshot,
            checksum=snapshot_checksum(snapshot),
            effective_at=model.effective_at,
            reason="INITIAL_ACTIVATION",
            created_by=self.ctx.user_id or None,
        )
        self.versions.add(LeaseContractVersionMapper.new_model(version, park_id=int(model.park_id)))
        self.schedules.replace_version(
            int(model.id),
            1,
            [LeasePerformanceScheduleMapper.new_model(row) for row in schedule],
        )
        self.contracts.save(model)
        for unit in unit_models:
            self.occupancy.recompute_unit_used_area(unit)
        for active_lock in consumed_locks:
            active_lock.status = "CONSUMED"
            active_lock.consumed_at = now
            active_lock.lock_version += 1
            self.session.add(active_lock)
        self.work_items.ensure_from_source(
            source_type="LEASE",
            source_id=str(model.id),
            item_type="CONTRACT_EXPIRING",
            title=f"合同即将到期 {model.contract_no}",
            park_id=int(model.park_id),
            priority="HIGH",
            due_at=datetime.combine(model.end_date, datetime.min.time()).isoformat(),
            commit=False,
        )
        self.audit.record(
            action="activate_v2",
            resource_type="LEASE_CONTRACT",
            resource_id=model.id,
            park_id=model.park_id,
            detail={
                "version_no": 1,
                "unit_ids": sorted(area_by_id),
                "schedule_count": len(schedule),
            },
        )
        self.session.commit()
        return self.detail(contract_id)

    def create_change(
        self,
        contract_id: int,
        *,
        expected_version: int,
        change_type: str,
        effective_date: Any,
        reason: str,
        proposed_snapshot: dict[str, Any],
        target_party_eligible: Optional[bool] = None,
    ) -> dict[str, Any]:
        self._permission("lease:change")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        if model.status not in {"ACTIVE", "EXPIRING"}:
            raise AppError("合同状态不可变更", code="LEASE_STATUS_INVALID", status_code=409)
        current = self._current_snapshot(model)
        effective = self._date(effective_date, "effective_date")
        boundaries = {
            row.period_start
            for row in self.schedules.list_for_contract(
                contract_id, version_no=int(model.current_version_no)
            )
        }
        normalized_change_type = str(change_type or "").strip().upper()
        verified_party_eligible = target_party_eligible
        if normalized_change_type == "PARTY_TRANSFER":
            target_party_id = int((proposed_snapshot.get("contract") or {}).get("party_id") or 0)
            target_party = self.parties.get_by_id(target_party_id) if target_party_id else None
            verified_party_eligible = bool(
                target_party is not None
                and target_party.status != "ARCHIVED"
                and target_party.risk_status != "BLACKLISTED"
            )
        validated = self._domain_call(
            validate_change_proposal,
            normalized_change_type,
            current_snapshot=current,
            proposed_snapshot=proposed_snapshot,
            effective_date=effective,
            reason=reason,
            cycle_boundaries=boundaries,
            target_party_eligible=verified_party_eligible,
        )
        from app.infrastructure.platform.number_sequence import next_number

        sequence = next_number(
            self.session,
            tenant_id=self.ctx.tenant_id,
            biz_type="LEASE_CHANGE",
            period_key=effective.strftime("%Y%m%d"),
        )
        entity = LeaseChangeOrderEntity(
            tenant_id=self.ctx.tenant_id,
            contract_id=contract_id,
            change_no=f"LCH{effective.strftime('%Y%m%d')}{sequence:04d}",
            change_type=validated["change_type"],
            reason=validated["reason"],
            effective_date=validated["effective_date"],
            base_version_no=int(model.current_version_no),
            proposed_snapshot=canonical_snapshot(validated["proposed_snapshot"]),
            created_by=self.ctx.user_id or None,
        )
        change = self.changes.add(
            LeaseChangeOrderMapper.new_model(entity, park_id=int(model.park_id))
        )
        model.lock_version += 1
        self.contracts.save(model)
        self.audit.record(
            action="create_change",
            resource_type="LEASE_CHANGE_ORDER",
            resource_id=change.id,
            park_id=model.park_id,
            detail={"change_type": change.change_type, "base_version_no": change.base_version_no},
        )
        self.session.commit()
        return self.detail(contract_id)

    def edit_change(
        self,
        change_id: int,
        *,
        expected_version: int,
        change_type: str,
        effective_date: Any,
        reason: str,
        proposed_snapshot: dict[str, Any],
        target_party_eligible: Optional[bool] = None,
    ) -> dict[str, Any]:
        self._permission("lease:change")
        change = self.changes.get(change_id, for_update=True)
        if change is None:
            raise AppError("变更单不存在", code="LEASE_CHANGE_NOT_FOUND", status_code=404)
        model = self._contract(int(change.contract_id), for_update=True)
        self._expected(model, expected_version)
        if change.status != "DRAFT":
            raise AppError("仅草稿变更可编辑", code="LEASE_CHANGE_STATUS_INVALID", status_code=409)
        self._domain_call(assert_base_version, model.current_version_no, change.base_version_no)
        effective = self._date(effective_date, "effective_date")
        boundaries = {
            row.period_start
            for row in self.schedules.list_for_contract(
                int(model.id), version_no=int(model.current_version_no)
            )
        }
        normalized_change_type = str(change_type or "").strip().upper()
        verified_party_eligible = target_party_eligible
        if normalized_change_type == "PARTY_TRANSFER":
            target_party_id = int((proposed_snapshot.get("contract") or {}).get("party_id") or 0)
            target_party = self.parties.get_by_id(target_party_id) if target_party_id else None
            verified_party_eligible = bool(
                target_party is not None
                and target_party.status != "ARCHIVED"
                and target_party.risk_status != "BLACKLISTED"
            )
        validated = self._domain_call(
            validate_change_proposal,
            normalized_change_type,
            current_snapshot=self._current_snapshot(model),
            proposed_snapshot=proposed_snapshot,
            effective_date=effective,
            reason=reason,
            cycle_boundaries=boundaries,
            target_party_eligible=verified_party_eligible,
        )
        canonical_proposal = canonical_snapshot(validated["proposed_snapshot"])
        change.change_type = validated["change_type"]
        change.reason = validated["reason"]
        change.effective_date = validated["effective_date"]
        change.proposal_json = canonical_proposal
        change.proposal_checksum = snapshot_checksum(canonical_proposal)
        change.proposal_schema_version = 1
        change.lock_version += 1
        model.lock_version += 1
        self.changes.save(change)
        self.contracts.save(model)
        self.audit.record(
            action="edit_change",
            resource_type="LEASE_CHANGE_ORDER",
            resource_id=change.id,
            park_id=model.park_id,
            detail={"change_type": change.change_type, "base_version_no": change.base_version_no},
        )
        self.session.commit()
        return self.detail(int(model.id))

    def submit_change(
        self, change_id: int, *, expected_version: int, remark: Optional[str]
    ) -> dict[str, Any]:
        self._permission("lease:change", "approval:write")
        change = self.changes.get(change_id, for_update=True)
        if change is None:
            raise AppError("变更单不存在", code="LEASE_CHANGE_NOT_FOUND", status_code=404)
        model = self._contract(int(change.contract_id), for_update=True)
        self._expected(model, expected_version)
        self._domain_call(assert_change_status_transition, change.status, "SUBMITTED")
        self._domain_call(assert_base_version, model.current_version_no, change.base_version_no)
        revision = int(change.lock_version) + 1
        approval = self.approvals.submit(
            park_id=int(model.park_id),
            biz_type="LEASE_CHANGE_ORDER",
            biz_id=f"{change.id}:r{revision}",
            title=f"合同变更审批 {model.contract_no}/{change.change_no}",
            remark=remark,
        )
        change.status = "SUBMITTED"
        change.approval_id = approval.id
        change.lock_version = revision
        self.changes.save(change)
        model.lock_version += 1
        self.contracts.save(model)
        self.work_items.ensure_from_source(
            source_type="LEASE_CHANGE_APPROVAL",
            source_id=str(approval.id),
            item_type="LEASE_CHANGE_APPROVAL",
            title=f"待审批合同变更 {change.change_no}",
            park_id=int(model.park_id),
            priority="HIGH",
            commit=False,
        )
        self.audit.record(
            action="submit_change",
            resource_type="LEASE_CHANGE_ORDER",
            resource_id=change.id,
            park_id=model.park_id,
            detail={"approval_id": approval.id},
        )
        self.session.commit()
        result = self.detail(int(model.id))
        result["pending_approval"] = {"id": approval.id, "status": approval.status}
        return result

    def decide_change(
        self,
        change_id: int,
        *,
        approve: bool,
        expected_version: int,
        remark: Optional[str],
        override_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        self._permission("approval:decide", "lease:approve")
        change = self.changes.get(change_id, for_update=True)
        if change is None:
            raise AppError("变更单不存在", code="LEASE_CHANGE_NOT_FOUND", status_code=404)
        model = self._contract(int(change.contract_id), for_update=True)
        self._expected(model, expected_version)
        self._domain_call(
            assert_change_status_transition,
            change.status,
            "APPROVED" if approve else "REJECTED",
        )
        if not change.approval_id:
            raise AppError("变更缺少审批", code="LEASE_APPROVAL_REQUIRED", status_code=409)
        self.approvals.decide(
            int(change.approval_id),
            approve=approve,
            remark=remark,
            override_reason=override_reason,
        )
        change.status = "APPROVED" if approve else "REJECTED"
        change.lock_version += 1
        self.changes.save(change)
        model.lock_version += 1
        self.contracts.save(model)
        self.work_items.complete_by_source(
            source_type="LEASE_CHANGE_APPROVAL",
            source_id=str(change.approval_id),
            item_type="LEASE_CHANGE_APPROVAL",
            commit=False,
        )
        if approve:
            self.work_items.ensure_from_source(
                source_type="LEASE_CHANGE",
                source_id=str(change.id),
                item_type="LEASE_CHANGE_DUE",
                title=f"合同变更待生效 {change.change_no}",
                park_id=int(model.park_id),
                priority="HIGH",
                due_at=datetime.combine(change.effective_date, datetime.min.time()).isoformat(),
                commit=False,
            )
        self.audit.record(
            action="approve_change" if approve else "reject_change",
            resource_type="LEASE_CHANGE_ORDER",
            resource_id=change.id,
            park_id=model.park_id,
            detail={"approval_id": change.approval_id, "override": bool(override_reason)},
        )
        self.session.commit()
        return self.detail(int(model.id))

    def withdraw_change(
        self,
        change_id: int,
        *,
        expected_version: int,
        remark: Optional[str],
    ) -> dict[str, Any]:
        self._permission("lease:change", "approval:write")
        change = self.changes.get(change_id, for_update=True)
        if change is None:
            raise AppError("变更单不存在", code="LEASE_CHANGE_NOT_FOUND", status_code=404)
        model = self._contract(int(change.contract_id), for_update=True)
        self._expected(model, expected_version)
        self._domain_call(assert_change_status_transition, change.status, "WITHDRAWN")
        if not change.approval_id:
            raise AppError("变更缺少审批", code="LEASE_APPROVAL_REQUIRED", status_code=409)
        self.approvals.withdraw(int(change.approval_id), remark=remark)
        change.status = "WITHDRAWN"
        change.lock_version += 1
        model.lock_version += 1
        self.changes.save(change)
        self.contracts.save(model)
        self.work_items.cancel_by_source(
            source_type="LEASE_CHANGE_APPROVAL",
            source_id=str(change.approval_id),
            item_type="LEASE_CHANGE_APPROVAL",
            commit=False,
        )
        self.audit.record(
            action="withdraw_change",
            resource_type="LEASE_CHANGE_ORDER",
            resource_id=change.id,
            park_id=model.park_id,
            detail={"approval_id": change.approval_id, "remark": remark},
        )
        self.session.commit()
        return self.detail(int(model.id))

    def cancel_change(
        self,
        change_id: int,
        *,
        expected_version: int,
        remark: Optional[str],
    ) -> dict[str, Any]:
        self._permission("lease:change")
        change = self.changes.get(change_id, for_update=True)
        if change is None:
            raise AppError("变更单不存在", code="LEASE_CHANGE_NOT_FOUND", status_code=404)
        model = self._contract(int(change.contract_id), for_update=True)
        self._expected(model, expected_version)
        self._domain_call(assert_change_status_transition, change.status, "CANCELLED")
        change.status = "CANCELLED"
        change.lock_version += 1
        model.lock_version += 1
        self.changes.save(change)
        self.contracts.save(model)
        if change.approval_id:
            self.work_items.cancel_by_source(
                source_type="LEASE_CHANGE_APPROVAL",
                source_id=str(change.approval_id),
                item_type="LEASE_CHANGE_APPROVAL",
                commit=False,
            )
        self.work_items.cancel_by_source(
            source_type="LEASE_CHANGE",
            source_id=str(change.id),
            item_type="LEASE_CHANGE_DUE",
            commit=False,
        )
        self.audit.record(
            action="cancel_change",
            resource_type="LEASE_CHANGE_ORDER",
            resource_id=change.id,
            park_id=model.park_id,
            detail={"remark": remark},
        )
        self.session.commit()
        return self.detail(int(model.id))

    def _create_exit_settlement(
        self,
        model,
        *,
        planned: date,
        inspection_summary: Optional[str] = None,
        change_order_id: Optional[int] = None,
    ):
        existing = self.exits.get_open_for_contract(int(model.id))
        if existing is not None:
            if (
                change_order_id is not None
                and int(existing.change_order_id or 0) == change_order_id
            ):
                return existing
            raise AppError("已有进行中的退租", code="LEASE_EXIT_IN_FLIGHT", status_code=409)
        billing = self.billing_outstanding.for_contract(int(model.id))
        calculation = self._domain_call(
            calculate_exit_totals,
            held_deposit_amount=model.deposit_amount,
            outstanding_amount=billing.amount,
            items=[],
        )
        from app.infrastructure.platform.number_sequence import next_number

        sequence = next_number(
            self.session,
            tenant_id=self.ctx.tenant_id,
            biz_type="LEASE_EXIT",
            period_key=planned.strftime("%Y%m%d"),
        )
        entity = LeaseExitSettlementEntity(
            tenant_id=self.ctx.tenant_id,
            contract_id=int(model.id),
            change_order_id=change_order_id,
            settlement_no=f"LEX{planned.strftime('%Y%m%d')}{sequence:04d}",
            contract_version_no=int(model.current_version_no),
            planned_handover_date=planned,
            held_deposit_amount=Decimal(str(model.deposit_amount or 0)),
            outstanding_amount=billing.amount,
            outstanding_source=billing.source,
            outstanding_as_of=billing.as_of.replace(tzinfo=None),
            inspection_summary=inspection_summary,
            receivable_total=calculation["receivable_total"],
            deduction_total=calculation["deduction_total"],
            refund_adjustment_total=calculation["refund_adjustment_total"],
            net_due_from_party=calculation["net_due_from_party"],
            net_due_to_party=calculation["net_due_to_party"],
            calculation_checksum=calculation["checksum"],
            created_by=self.ctx.user_id or None,
        )
        return self.exits.add(
            LeaseExitSettlementMapper.new_model(entity, park_id=int(model.park_id))
        )

    def create_exit(
        self,
        contract_id: int,
        *,
        expected_version: int,
        handover_date: Any,
        inspection_summary: Optional[str] = None,
    ) -> dict[str, Any]:
        self._permission("lease:settle")
        model = self._contract(contract_id, for_update=True)
        self._expected(model, expected_version)
        if model.status not in {"ACTIVE", "EXPIRING"}:
            raise AppError("合同状态不可退租", code="LEASE_STATUS_INVALID", status_code=409)
        planned = self._date(handover_date, "handover_date")
        settlement = self._create_exit_settlement(
            model,
            planned=planned,
            inspection_summary=inspection_summary,
        )
        model.lock_version += 1
        self.contracts.save(model)
        self.audit.record(
            action="create_exit",
            resource_type="LEASE_EXIT_SETTLEMENT",
            resource_id=settlement.id,
            park_id=model.park_id,
            detail={
                "contract_version_no": model.current_version_no,
                "outstanding_source": settlement.outstanding_source,
                "billing_effect": "NONE",
            },
        )
        self.session.commit()
        return self.detail(contract_id)

    def edit_exit(
        self,
        settlement_id: int,
        *,
        expected_version: int,
        meter_readings: list[dict[str, Any]],
        items: list[dict[str, Any]],
        inspection_summary: Optional[str],
    ) -> dict[str, Any]:
        self._permission("lease:settle")
        settlement = self.exits.get(settlement_id, for_update=True)
        if settlement is None:
            raise AppError("退租结算不存在", code="LEASE_EXIT_NOT_FOUND", status_code=404)
        if int(settlement.lock_version) != int(expected_version):
            raise AppError("退租版本冲突", code="LEASE_VERSION_CONFLICT", status_code=409)
        if settlement.status != "DRAFT":
            raise AppError("退租结算不可编辑", code="LEASE_EXIT_STATUS_INVALID", status_code=409)
        normalized_items: list[LeaseExitItemEntity] = []
        for index, raw in enumerate(items):
            evidence_id = raw.get("evidence_attachment_id")
            if evidence_id is not None:
                attachment = self.attachments.get(int(evidence_id))
                if (
                    attachment is None
                    or attachment.status != "ACTIVE"
                    or attachment.biz_type != "LEASE_EXIT_SETTLEMENT"
                    or attachment.biz_id != str(settlement.id)
                ):
                    raise AppError("结算证据不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
            normalized_items.append(
                LeaseExitItemEntity(
                    tenant_id=self.ctx.tenant_id,
                    settlement_id=int(settlement.id),
                    item_type=str(raw.get("item_type") or ""),
                    amount=Decimal(str(raw.get("amount") or 0)),
                    description=str(raw.get("description") or ""),
                    approved=bool(raw.get("approved", True)),
                    evidence_attachment_id=(int(evidence_id) if evidence_id is not None else None),
                    source_type=raw.get("source_type"),
                    source_ref=raw.get("source_ref"),
                    sort_order=int(raw.get("sort_order", index)),
                )
            )
        calculation = self._domain_call(
            calculate_exit_totals,
            held_deposit_amount=settlement.held_deposit_amount,
            outstanding_amount=settlement.outstanding_amount,
            items=normalized_items,
            meter_readings=meter_readings,
        )
        settlement.inspection_summary = inspection_summary
        settlement.meter_readings_json = canonical_value(calculation["meter_readings"])
        settlement.receivable_total = calculation["receivable_total"]
        settlement.deduction_total = calculation["deduction_total"]
        settlement.refund_adjustment_total = calculation["refund_adjustment_total"]
        settlement.net_due_from_party = calculation["net_due_from_party"]
        settlement.net_due_to_party = calculation["net_due_to_party"]
        settlement.checksum = calculation["checksum"]
        settlement.lock_version += 1
        self.exits.save(settlement)
        self.exit_items.replace_for_settlement(
            int(settlement.id),
            [LeaseExitItemMapper.new_model(entity) for entity in normalized_items],
        )
        self.audit.record(
            action="edit_exit",
            resource_type="LEASE_EXIT_SETTLEMENT",
            resource_id=settlement.id,
            park_id=settlement.park_id,
            detail={"item_count": len(normalized_items), "meter_count": len(meter_readings)},
        )
        self.session.commit()
        return self.detail(int(settlement.contract_id))

    def submit_exit(
        self,
        settlement_id: int,
        *,
        expected_version: int,
        contract_expected_version: int,
        remark: Optional[str],
    ) -> dict[str, Any]:
        self._permission("lease:settle", "approval:write")
        settlement = self.exits.get(settlement_id, for_update=True)
        if settlement is None:
            raise AppError("退租结算不存在", code="LEASE_EXIT_NOT_FOUND", status_code=404)
        model = self._contract(int(settlement.contract_id), for_update=True)
        self._expected(model, contract_expected_version)
        if int(settlement.lock_version) != int(expected_version):
            raise AppError("退租版本冲突", code="LEASE_VERSION_CONFLICT", status_code=409)
        self._domain_call(assert_exit_status_transition, settlement.status, "SUBMITTED")
        self._domain_call(assert_v2_status_transition, model.status, "EXIT_PENDING")
        approval = self.approvals.submit(
            park_id=int(model.park_id),
            biz_type="LEASE_EXIT_SETTLEMENT",
            biz_id=f"{settlement.id}:r{settlement.lock_version + 1}",
            title=f"退租结算审批 {model.contract_no}/{settlement.settlement_no}",
            remark=remark,
        )
        settlement.status = "SUBMITTED"
        settlement.approval_id = approval.id
        settlement.lock_version += 1
        model.status = "EXIT_PENDING"
        model.lock_version += 1
        self.exits.save(settlement)
        self.contracts.save(model)
        self.work_items.ensure_from_source(
            source_type="LEASE_EXIT_APPROVAL",
            source_id=str(approval.id),
            item_type="LEASE_EXIT_APPROVAL",
            title=f"待审批退租结算 {settlement.settlement_no}",
            park_id=int(model.park_id),
            priority="HIGH",
            commit=False,
        )
        self.audit.record(
            action="submit_exit",
            resource_type="LEASE_EXIT_SETTLEMENT",
            resource_id=settlement.id,
            park_id=model.park_id,
            detail={"approval_id": approval.id},
        )
        self.session.commit()
        result = self.detail(int(model.id))
        result["pending_approval"] = {"id": approval.id, "status": approval.status}
        return result

    def decide_exit(
        self,
        settlement_id: int,
        *,
        approve: bool,
        expected_version: int,
        remark: Optional[str],
        override_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        self._permission("approval:decide", "lease:approve")
        settlement = self.exits.get(settlement_id, for_update=True)
        if settlement is None:
            raise AppError("退租结算不存在", code="LEASE_EXIT_NOT_FOUND", status_code=404)
        model = self._contract(int(settlement.contract_id), for_update=True)
        if int(settlement.lock_version) != int(expected_version):
            raise AppError("退租版本冲突", code="LEASE_VERSION_CONFLICT", status_code=409)
        target = "APPROVED" if approve else "REJECTED"
        self._domain_call(assert_exit_status_transition, settlement.status, target)
        if not settlement.approval_id:
            raise AppError("退租结算缺少审批", code="LEASE_APPROVAL_REQUIRED", status_code=409)
        self.approvals.decide(
            int(settlement.approval_id),
            approve=approve,
            remark=remark,
            override_reason=override_reason,
        )
        settlement.status = target
        settlement.lock_version += 1
        self.exits.save(settlement)
        restored_status: Optional[str] = None
        if not approve:
            current_version = self.versions.get(int(model.id), int(model.current_version_no))
            snapshot_status = (
                str((current_version.snapshot_json or {}).get("contract", {}).get("status") or "")
                if current_version is not None
                else ""
            )
            restored_status = (
                snapshot_status if snapshot_status in {"ACTIVE", "EXPIRING"} else "ACTIVE"
            )
            self._domain_call(assert_v2_status_transition, model.status, restored_status)
            model.status = restored_status
            model.lock_version += 1
            self.contracts.save(model)
        self.work_items.complete_by_source(
            source_type="LEASE_EXIT_APPROVAL",
            source_id=str(settlement.approval_id),
            item_type="LEASE_EXIT_APPROVAL",
            commit=False,
        )
        self.audit.record(
            action="approve_exit" if approve else "reject_exit",
            resource_type="LEASE_EXIT_SETTLEMENT",
            resource_id=settlement.id,
            park_id=settlement.park_id,
            detail={"override": bool(override_reason), "restored_contract_status": restored_status},
        )
        self.session.commit()
        return self.detail(int(settlement.contract_id))

    def withdraw_exit(
        self,
        settlement_id: int,
        *,
        expected_version: int,
        contract_expected_version: int,
        remark: Optional[str],
    ) -> dict[str, Any]:
        self._permission("lease:settle", "approval:write")
        settlement = self.exits.get(settlement_id, for_update=True)
        if settlement is None:
            raise AppError("退租结算不存在", code="LEASE_EXIT_NOT_FOUND", status_code=404)
        model = self._contract(int(settlement.contract_id), for_update=True)
        self._expected(model, contract_expected_version)
        if int(settlement.lock_version) != int(expected_version):
            raise AppError("退租版本冲突", code="LEASE_VERSION_CONFLICT", status_code=409)
        self._domain_call(assert_exit_status_transition, settlement.status, "WITHDRAWN")
        if not settlement.approval_id:
            raise AppError("退租结算缺少审批", code="LEASE_APPROVAL_REQUIRED", status_code=409)
        self.approvals.withdraw(int(settlement.approval_id), remark=remark)
        current_version = self.versions.get(int(model.id), int(model.current_version_no))
        snapshot_status = (
            str((current_version.snapshot_json or {}).get("contract", {}).get("status") or "")
            if current_version is not None
            else ""
        )
        restored_status = snapshot_status if snapshot_status in {"ACTIVE", "EXPIRING"} else "ACTIVE"
        self._domain_call(assert_v2_status_transition, model.status, restored_status)
        settlement.status = "WITHDRAWN"
        settlement.lock_version += 1
        model.status = restored_status
        model.lock_version += 1
        self.exits.save(settlement)
        self.contracts.save(model)
        self.work_items.cancel_by_source(
            source_type="LEASE_EXIT_APPROVAL",
            source_id=str(settlement.approval_id),
            item_type="LEASE_EXIT_APPROVAL",
            commit=False,
        )
        self.audit.record(
            action="withdraw_exit",
            resource_type="LEASE_EXIT_SETTLEMENT",
            resource_id=settlement.id,
            park_id=model.park_id,
            detail={"restored_contract_status": restored_status, "remark": remark},
        )
        self.session.commit()
        return self.detail(int(model.id))

    def confirm_clearance(
        self,
        settlement_id: int,
        *,
        expected_version: int,
        evidence_attachment_id: int,
        reference: str,
        reason: str,
    ) -> dict[str, Any]:
        self._permission("lease:finance_clearance")
        settlement = self.exits.get(settlement_id, for_update=True)
        if settlement is None:
            raise AppError("退租结算不存在", code="LEASE_EXIT_NOT_FOUND", status_code=404)
        if int(settlement.lock_version) != int(expected_version):
            raise AppError("退租版本冲突", code="LEASE_VERSION_CONFLICT", status_code=409)
        if settlement.status != "APPROVED":
            raise AppError("结算尚未批准", code="LEASE_EXIT_STATUS_INVALID", status_code=409)
        attachment = self.attachments.get(int(evidence_attachment_id))
        if (
            attachment is None
            or attachment.status != "ACTIVE"
            or attachment.biz_type != "LEASE_EXIT_SETTLEMENT"
            or attachment.biz_id != str(settlement.id)
        ):
            raise AppError("清算证据不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
        if not (reference or "").strip() or not (reason or "").strip():
            raise AppError(
                "清算引用和原因必填", code="LEASE_FINANCIAL_CLEARANCE_REQUIRED", status_code=400
            )
        settlement.financial_clearance_status = "CONFIRMED"
        settlement.clearance_evidence_attachment_id = int(evidence_attachment_id)
        settlement.clearance_reference = reference.strip()
        settlement.clearance_reason = reason.strip()
        settlement.clearance_by = self.ctx.user_id or None
        settlement.clearance_at = utc_now()
        settlement.lock_version += 1
        self.exits.save(settlement)
        self.audit.record(
            action="confirm_clearance",
            resource_type="LEASE_EXIT_SETTLEMENT",
            resource_id=settlement.id,
            park_id=settlement.park_id,
            detail={"reference": reference[:64], "financial_effect": "NONE"},
        )
        self.session.commit()
        return self.detail(int(settlement.contract_id))

    def close_exit(
        self,
        settlement_id: int,
        *,
        expected_version: int,
        contract_expected_version: int,
        idempotency_key: str,
        breached: bool = False,
    ) -> dict[str, Any]:
        self._permission("lease:settle")
        from app.modules.lease.domain.versioning import scoped_idempotency_key

        scoped_key = self._domain_call(
            scoped_idempotency_key, self.ctx.tenant_id, "CLOSE_EXIT", idempotency_key
        )
        replay = self.exits.find_replay(scoped_key)
        if replay is not None and replay.status == "CLOSED":
            return self.detail(int(replay.contract_id))
        settlement = self.exits.get(settlement_id, for_update=True)
        if settlement is None:
            raise AppError("退租结算不存在", code="LEASE_EXIT_NOT_FOUND", status_code=404)
        # Re-check after the settlement row lock: a concurrent retry can have
        # missed the optimistic replay lookup and then waited for the winner.
        if settlement.status == "CLOSED" and settlement.idempotency_key == scoped_key:
            return self.detail(int(settlement.contract_id))
        model = self._contract(int(settlement.contract_id), for_update=True)
        self._expected(model, contract_expected_version)
        if int(settlement.lock_version) != int(expected_version):
            raise AppError("退租版本冲突", code="LEASE_VERSION_CONFLICT", status_code=409)
        self._domain_call(assert_exit_status_transition, settlement.status, "CLOSED")
        self._domain_call(
            assert_financial_clearance,
            net_due_from_party=settlement.net_due_from_party,
            net_due_to_party=settlement.net_due_to_party,
            status=settlement.financial_clearance_status,
            evidence_ref=settlement.clearance_reference,
            reason=settlement.clearance_reason,
        )
        exit_documents = [
            row
            for row in self.documents.list_for_contract(int(model.id))
            if int(row.exit_settlement_id or 0) == int(settlement.id)
            and row.status in {"APPROVED", "SIGNED"}
        ]
        if not exit_documents:
            raise AppError("缺少已批准退租文档", code="LEASE_DOCUMENT_REQUIRED", status_code=409)
        lines = self.units.list_for_contract(int(model.id))
        unit_models = lock_current_units(self.session, [row.unit_id for row in lines])
        if len(unit_models) != len(lines):
            raise AppError("单元版本已变化", code="OCCUPANCY_CONFLICT", status_code=409)
        terminal_status = "BREACHED" if breached else "TERMINATED"
        self._domain_call(assert_v2_status_transition, model.status, terminal_status)
        model.status = terminal_status
        model.terminated_at = utc_now()
        model.current_version_no += 1
        model.lock_version += 1
        snapshot = self._current_snapshot(model)
        snapshot["exit_settlement"] = {
            "id": settlement.id,
            "settlement_no": settlement.settlement_no,
            "checksum": settlement.checksum,
            "net_due_from_party": str(settlement.net_due_from_party),
            "net_due_to_party": str(settlement.net_due_to_party),
            "financial_clearance_status": settlement.financial_clearance_status,
        }
        snapshot = canonical_snapshot(snapshot)
        version = LeaseContractVersionEntity(
            tenant_id=self.ctx.tenant_id,
            contract_id=int(model.id),
            version_no=int(model.current_version_no),
            schema_version=1,
            snapshot=snapshot,
            checksum=snapshot_checksum(snapshot),
            effective_at=model.terminated_at,
            reason="BREACH_EXIT_CLOSE" if breached else "EXIT_CLOSE",
            created_by=self.ctx.user_id or None,
            exit_settlement_id=int(settlement.id),
        )
        self.versions.add(LeaseContractVersionMapper.new_model(version, park_id=int(model.park_id)))
        settlement.status = "CLOSED"
        settlement.idempotency_key = scoped_key
        settlement.closed_at = utc_now()
        settlement.lock_version += 1
        self.exits.save(settlement)
        self.contracts.save(model)
        for unit in unit_models:
            self.occupancy.recompute_unit_used_area(unit)
        self.work_items.cancel_by_source(
            source_type="LEASE",
            source_id=str(model.id),
            item_type="CONTRACT_EXPIRING",
            commit=False,
        )
        self.audit.record(
            action="close_exit",
            resource_type="LEASE_EXIT_SETTLEMENT",
            resource_id=settlement.id,
            park_id=model.park_id,
            detail={
                "terminal_status": terminal_status,
                "version_no": model.current_version_no,
                "unit_ids": sorted(int(row.id) for row in unit_models),
                "financial_effect": "NONE",
            },
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("退租关闭冲突", code="LEASE_EXIT_IN_FLIGHT", status_code=409) from exc
        return self.detail(int(model.id))

    def apply_change(
        self,
        change_id: int,
        *,
        expected_version: int,
        idempotency_key: str,
        as_of: Optional[date] = None,
    ) -> dict[str, Any]:
        self._permission("lease:change")
        from app.modules.lease.domain.versioning import scoped_idempotency_key

        scoped_key = self._domain_call(
            scoped_idempotency_key, self.ctx.tenant_id, "APPLY_CHANGE", idempotency_key
        )
        replay = self.changes.find_replay(scoped_key)
        if replay is not None and replay.status == "APPLIED":
            return self.detail(int(replay.contract_id))
        change = self.changes.get(change_id, for_update=True)
        if change is None:
            raise AppError("变更单不存在", code="LEASE_CHANGE_NOT_FOUND", status_code=404)
        # A concurrent retry can miss the optimistic replay read above, wait on
        # this row lock, and then observe the first transaction's committed
        # result. Re-check under the lock before validating the now-incremented
        # aggregate version so the same idempotency key returns the first result.
        if change.status == "APPLIED" and change.idempotency_key == scoped_key:
            return self.detail(int(change.contract_id))
        model = self._contract(int(change.contract_id), for_update=True)
        self._expected(model, expected_version)
        if change.status != "APPROVED":
            raise AppError("变更单未批准", code="LEASE_APPROVAL_REQUIRED", status_code=409)
        if change.effective_date > (as_of or date.today()):
            raise AppError("变更尚未到生效日", code="LEASE_CHANGE_NOT_DUE", status_code=409)
        self._domain_call(assert_base_version, model.current_version_no, change.base_version_no)

        proposal = canonical_snapshot(dict(change.proposal_json))
        contract_data = proposal["contract"]
        proposed_units = proposal.get("units") or []
        old_unit_ids = [row.unit_id for row in self.units.list_for_contract(int(model.id))]
        new_unit_ids = [int(row["unit_id"]) for row in proposed_units]
        locked_units = lock_current_units(self.session, old_unit_ids + new_unit_ids)
        locked_by_id = {int(row.id): row for row in locked_units}
        if any(unit_id not in locked_by_id for unit_id in set(old_unit_ids + new_unit_ids)):
            raise AppError("单元版本已变化", code="OCCUPANCY_CONFLICT", status_code=409)

        new_contract_units = [
            LeaseContractUnitMapper.new_model(
                LeaseContractUnitEntity(
                    tenant_id=self.ctx.tenant_id,
                    contract_id=int(model.id),
                    unit_id=int(raw["unit_id"]),
                    occupied_area=Decimal(str(raw["occupied_area"])),
                    unit_rent_price=Decimal(str(raw.get("unit_rent_price") or 0)),
                )
            )
            for raw in proposed_units
        ]
        self.occupancy.assert_can_activate_lines(
            contract_id=int(model.id),
            lines=[
                (locked_by_id[int(row.unit_id)], Decimal(str(row.occupied_area)))
                for row in new_contract_units
            ],
        )
        charge_models = []
        for index, raw in enumerate(proposal.get("charges") or []):
            raw_config = raw.get("rule_config") or {}
            charge_models.append(
                LeaseChargeItemMapper.new_model(
                    LeaseChargeItemEntity(
                        tenant_id=self.ctx.tenant_id,
                        contract_id=int(model.id),
                        charge_code=str(raw["charge_code"]),
                        charge_type=str(raw["charge_type"]),
                        calculation_method=str(raw["calculation_method"]),
                        billing_cycle=str(raw["billing_cycle"]),
                        currency=str(raw.get("currency") or model.currency),
                        start_date=self._date(raw["start_date"], "start_date"),
                        end_date=self._date(raw["end_date"], "end_date"),
                        due_day=int(raw.get("due_day") or 1),
                        amount=(
                            Decimal(str(raw["amount"])) if raw.get("amount") is not None else None
                        ),
                        unit_price=(
                            Decimal(str(raw["unit_price"]))
                            if raw.get("unit_price") is not None
                            else None
                        ),
                        tax_rate=Decimal(str(raw.get("tax_rate") or 0)),
                        sort_order=int(raw.get("sort_order", index)),
                        rule_config=raw_config,
                    )
                )
            )
        self.units.delete_for_contract(int(model.id))
        for row in new_contract_units:
            self.units.add(row)
        self.charges.replace_for_contract(int(model.id), charge_models)

        model.party_id = int(contract_data["party_id"])
        model.start_date = self._date(contract_data["start_date"], "start_date")
        model.end_date = self._date(contract_data["end_date"], "end_date")
        model.deposit_amount = Decimal(str(contract_data.get("deposit_amount") or 0))
        next_version = int(model.current_version_no) + 1
        schedule = self._generate_schedule(model, version_no=next_version)
        if change.change_type == "EARLY_TERMINATION":
            self._domain_call(assert_v2_status_transition, model.status, "EXIT_PENDING")
            model.status = "EXIT_PENDING"
        model.current_version_no = next_version
        model.lock_version += 1
        version_snapshot = self._snapshot(model, schedule)
        version = LeaseContractVersionEntity(
            tenant_id=self.ctx.tenant_id,
            contract_id=int(model.id),
            version_no=next_version,
            schema_version=1,
            snapshot=version_snapshot,
            checksum=snapshot_checksum(version_snapshot),
            effective_at=datetime.combine(change.effective_date, datetime.min.time()),
            reason=f"CHANGE_{change.change_type}",
            created_by=self.ctx.user_id or None,
            change_order_id=int(change.id),
        )
        self.versions.add(LeaseContractVersionMapper.new_model(version, park_id=int(model.park_id)))
        self.schedules.replace_version(
            int(model.id),
            next_version,
            [LeasePerformanceScheduleMapper.new_model(row) for row in schedule],
        )
        linked_exit = None
        if change.change_type == "EARLY_TERMINATION":
            linked_exit = self._create_exit_settlement(
                model,
                planned=change.effective_date,
                inspection_summary=f"由提前退租变更 {change.change_no} 自动创建",
                change_order_id=int(change.id),
            )
            self.work_items.ensure_from_source(
                source_type="LEASE_EXIT_SETTLEMENT",
                source_id=str(linked_exit.id),
                item_type="LEASE_EXIT_HANDOVER",
                title=f"待办理退租交接 {linked_exit.settlement_no}",
                park_id=int(model.park_id),
                priority="HIGH",
                due_at=datetime.combine(change.effective_date, datetime.min.time()).isoformat(),
                commit=False,
            )
        change.status = "APPLIED"
        change.applied_version_no = next_version
        change.idempotency_key = scoped_key
        change.applied_at = utc_now()
        change.lock_version += 1
        self.changes.save(change)
        self.contracts.save(model)
        for unit in locked_units:
            self.occupancy.recompute_unit_used_area(unit)
        self.work_items.complete_by_source(
            source_type="LEASE_CHANGE",
            source_id=str(change.id),
            item_type="LEASE_CHANGE_DUE",
            commit=False,
        )
        self.audit.record(
            action="apply_change",
            resource_type="LEASE_CHANGE_ORDER",
            resource_id=change.id,
            park_id=model.park_id,
            detail={
                "prior_version_no": next_version - 1,
                "new_version_no": next_version,
                "unit_ids": sorted(set(old_unit_ids + new_unit_ids)),
                "exit_settlement_id": linked_exit.id if linked_exit is not None else None,
            },
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("变更应用冲突", code="LEASE_CHANGE_IN_FLIGHT", status_code=409) from exc
        return self.detail(int(model.id))

    def apply_due(self, *, as_of: Optional[date] = None, limit: int = 100) -> dict[str, Any]:
        """Apply locally invoked due changes; this is not a production scheduler."""

        self._permission("lease:change")
        effective_day = as_of or date.today()
        bounded_limit = max(1, min(int(limit), 200))
        due = self.changes.list_due_approved(effective_day)[:bounded_limit]
        applied: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for row in due:
            model = self._contract(int(row.contract_id))
            try:
                result = self.apply_change(
                    int(row.id),
                    expected_version=int(model.lock_version),
                    idempotency_key=f"apply-due:{row.id}:v{row.base_version_no}",
                    as_of=effective_day,
                )
                applied.append(
                    {
                        "change_id": int(row.id),
                        "contract_id": int(row.contract_id),
                        "version_no": int(result["contract"]["current_version_no"]),
                    }
                )
            except AppError as exc:
                self.session.rollback()
                failed.append(
                    {
                        "change_id": int(row.id),
                        "contract_id": int(row.contract_id),
                        "code": exc.code,
                        "message": exc.message,
                    }
                )
        return {
            "as_of": effective_day.isoformat(),
            "processed": len(applied) + len(failed),
            "applied": applied,
            "failed": failed,
            "invocation_scope": "LOCAL_MANUAL",
        }

    def detail(self, contract_id: int) -> dict[str, Any]:
        self._permission("lease:read")
        model = self._contract(contract_id)
        versions = self.versions.list_for_contract(contract_id)
        charges = self.charges.list_for_contract(contract_id)
        schedules = self.schedules.list_for_contract(contract_id)
        documents = self.documents.list_for_contract(contract_id)
        change_rows = self.changes.list_for_contract(contract_id)
        exit_rows = self.exits.list_for_contract(contract_id)
        related_approval_ids = {
            int(approval_id)
            for approval_id in [
                *(row.approval_id for row in versions),
                *(row.approval_id for row in change_rows),
                *(row.approval_id for row in exit_rows),
            ]
            if approval_id is not None
        }
        approval_timeline = self.approvals.timeline_for_contract(
            contract_id, related_approval_ids=related_approval_ids
        )
        approval_ids = [row["approval_id"] for row in approval_timeline]
        return {
            "contract": {
                "id": model.id,
                "park_id": model.park_id,
                "party_id": model.party_id,
                "contract_no": model.contract_no,
                "contract_type": model.contract_type,
                "currency": model.currency,
                "status": model.status,
                "approval_status": model.approval_status,
                "start_date": model.start_date.isoformat(),
                "end_date": model.end_date.isoformat(),
                "deposit_amount": str(model.deposit_amount),
                "current_version_no": model.current_version_no,
                "lock_version": model.lock_version,
            },
            "units": [
                {
                    "id": row.id,
                    "unit_id": row.unit_id,
                    "occupied_area": str(row.occupied_area),
                    "unit_rent_price": str(row.unit_rent_price),
                }
                for row in self.units.list_for_contract(contract_id)
            ],
            "charges": [
                {
                    **asdict(LeaseChargeItemMapper.to_entity(row)),
                    "amount": str(row.amount) if row.amount is not None else None,
                    "unit_price": str(row.unit_price) if row.unit_price is not None else None,
                    "tax_rate": str(row.tax_rate),
                    "start_date": row.start_date.isoformat(),
                    "end_date": row.end_date.isoformat(),
                }
                for row in charges
            ],
            "schedules": [
                self._schedule_dict(LeasePerformanceScheduleMapper.to_entity(row))
                for row in schedules
            ],
            "versions": [
                {
                    "version_no": row.version_no,
                    "status": row.status,
                    "schema_version": row.schema_version,
                    "checksum": row.checksum,
                    "reason": row.reason,
                    "effective_at": row.effective_at.isoformat() if row.effective_at else None,
                }
                for row in versions
            ],
            "documents": [
                {
                    "id": row.id,
                    "attachment_id": row.attachment_id,
                    "document_type": row.document_type,
                    "document_version": row.document_version,
                    "status": row.status,
                    "checksum": row.checksum,
                    "is_main": row.is_main,
                    "contract_version_no": row.contract_version_no,
                    "change_order_id": row.change_order_id,
                    "exit_settlement_id": row.exit_settlement_id,
                    "signature_provider": row.signature_provider,
                    "live_verified": row.live_verified,
                }
                for row in documents
            ],
            "changes": [
                {
                    "id": row.id,
                    "change_no": row.change_no,
                    "change_type": row.change_type,
                    "status": row.status,
                    "reason": row.reason,
                    "effective_date": row.effective_date.isoformat(),
                    "base_version_no": row.base_version_no,
                    "applied_version_no": row.applied_version_no,
                    "proposal": canonical_value(row.proposal_json),
                    "proposal_checksum": row.proposal_checksum,
                    "proposal_schema_version": row.proposal_schema_version,
                    "lock_version": row.lock_version,
                    "approval_id": row.approval_id,
                }
                for row in change_rows
            ],
            "exit_settlement": self._exit_dict(exit_rows[0]) if exit_rows else None,
            "approval_ids": approval_ids,
            "approval_timeline": approval_timeline,
            "current_snapshot": (
                dict(versions[-1].snapshot_json) if versions else self._current_snapshot(model)
            ),
            "billing_effect": "NONE",
        }
