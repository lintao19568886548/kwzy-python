"""Supply application orchestration over pure rules and scoped repositories."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.supply.domain.rules import (
    approval_state,
    canonical_hash,
    clean_text,
    credential_projection,
    naive_utc,
    nonnegative_decimal,
    normalize_code,
    normalize_identifier,
    positive_decimal,
    require_version,
)
from app.modules.supply.infrastructure.repository import SupplyRepository
from app.modules.workflow.application.approval_service import ApprovalService
from app.shared.tenant_context import TenantContext


class SupplyService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = SupplyRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.approvals = ApprovalService(session, ctx)
        settings = get_settings()
        self._fingerprint_secret = settings.pii_fingerprint_secret or settings.jwt_secret

    def _permission(self, *codes: str) -> None:
        if any(self.ctx.has_permission(code) for code in codes):
            return
        raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def _park(self, value: Any) -> int:
        park_id = int(value)
        if self.repo.park(park_id) is None:
            raise AppError("资源不存在", code="RESOURCE_NOT_FOUND", status_code=404)
        return park_id

    def _commit(self, code: str, message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    @staticmethod
    def _number(prefix: str, key: str) -> str:
        return f"{prefix}-{utc_now():%Y%m%d}-{canonical_hash(key)[:10].upper()}"

    @staticmethod
    def _supplier_dict(row, *, scopes=(), qualifications=(), evaluations=()) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "party_id": int(row.party_id),
            "code": row.code,
            "display_name": row.display_name,
            "status": row.status,
            "lock_version": int(row.lock_version),
            "scopes": [
                {
                    "id": int(item.id),
                    "park_id": int(item.park_id),
                    "service_type": item.service_type,
                    "status": item.status,
                }
                for item in scopes
            ],
            "qualifications": [
                {
                    "id": int(item.id),
                    "qualification_type": item.qualification_type,
                    "credential_masked": item.credential_masked,
                    "issuer": item.issuer,
                    "effective_on": item.effective_on.isoformat(),
                    "expires_on": item.expires_on.isoformat() if item.expires_on else None,
                    "status": item.status,
                    "attachment_id": item.attachment_id,
                }
                for item in qualifications
            ],
            "evaluations": [
                {
                    "id": int(item.id),
                    "park_id": int(item.park_id),
                    "source_type": item.source_type,
                    "source_id": int(item.source_id),
                    "score": int(item.score),
                    "comment": item.comment,
                    "evaluated_at": item.evaluated_at.isoformat(),
                }
                for item in evaluations
            ],
        }

    @staticmethod
    def _material_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "code": row.code,
            "name": row.name,
            "category": row.category,
            "unit": row.unit,
            "reorder_point": str(row.reorder_point),
            "status": row.status,
        }

    @staticmethod
    def _warehouse_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "code": row.code,
            "name": row.name,
            "status": row.status,
        }

    @staticmethod
    def _balance_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "warehouse_id": int(row.warehouse_id),
            "material_id": int(row.material_id),
            "on_hand_qty": str(row.on_hand_qty),
            "reserved_qty": str(row.reserved_qty),
            "available_qty": str(Decimal(row.on_hand_qty) - Decimal(row.reserved_qty)),
            "lock_version": int(row.lock_version),
        }

    @staticmethod
    def _movement_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "balance_id": int(row.balance_id),
            "warehouse_id": int(row.warehouse_id),
            "material_id": int(row.material_id),
            "movement_type": row.movement_type,
            "quantity": str(row.quantity),
            "reference_type": row.reference_type,
            "reference_id": int(row.reference_id),
            "reverses_movement_id": row.reverses_movement_id,
            "occurred_at": row.occurred_at.isoformat(),
        }

    def overview(self) -> dict[str, Any]:
        self._permission("supply:read")
        balances = self.repo.balances()
        return {
            "active_suppliers": self.repo.count_suppliers(status="ACTIVE", keyword=None),
            "pending_procurement": sum(
                row.status == "PENDING_APPROVAL" for row in self.repo.list_requisitions()
            ),
            "low_stock_items": sum(
                Decimal(row.on_hand_qty)
                <= Decimal(self.repo.material(row.material_id).reorder_point)
                for row in balances
                if self.repo.material(row.material_id)
            ),
            "open_outsourcing": sum(
                row.status not in {"ACCEPTED", "CANCELLED", "REJECTED"}
                for row in self.repo.list_outsourcing()
            ),
            "external_integrations": {
                "erp": "NOT_CONNECTED",
                "wms": "NOT_CONNECTED",
                "supplier_portal": "NOT_CONNECTED",
                "production_contacted": False,
            },
            "legacy_data_migration": {
                "status": "BLOCKED",
                "reason": "AUTHORITATIVE_EXPORT_REQUIRED",
            },
        }

    def list_suppliers(
        self, *, page: int, page_size: int, status: str | None, keyword: str | None
    ) -> dict[str, Any]:
        self._permission("supply:read")
        rows = self.repo.list_suppliers(
            status=status, keyword=keyword, offset=(page - 1) * page_size, limit=page_size
        )
        return {
            "total": self.repo.count_suppliers(status=status, keyword=keyword),
            "page": page,
            "page_size": page_size,
            "items": [
                self._supplier_dict(
                    row,
                    scopes=self.repo.supplier_scopes(row.id),
                    qualifications=self.repo.supplier_qualifications(row.id),
                    evaluations=self.repo.supplier_evaluations(row.id),
                )
                for row in rows
            ],
        }

    def supplier_detail(self, supplier_id: int) -> dict[str, Any]:
        self._permission("supply:read")
        row = self.repo.supplier(supplier_id)
        if row is None:
            raise AppError("供应商不存在", code="SUPPLIER_NOT_FOUND", status_code=404)
        scopes = [
            item
            for item in self.repo.supplier_scopes(row.id)
            if self.ctx.allows_park(int(item.park_id))
        ]
        return self._supplier_dict(
            row,
            scopes=scopes,
            qualifications=self.repo.supplier_qualifications(row.id),
            evaluations=self.repo.supplier_evaluations(row.id),
        )

    def create_supplier(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("supplier:manage")
        party = self.repo.supplier_party(int(data["party_id"]))
        if party is None:
            raise AppError(
                "有效供应商企业主体不存在", code="SUPPLIER_PARTY_INVALID", status_code=404
            )
        row = self.repo.create_supplier(
            party_id=party.id,
            code=normalize_code(data["code"]),
            display_name=clean_text(
                data.get("display_name") or party.name, field="display_name", maximum=128
            ),
            status="ACTIVE",
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="create",
            resource_type="SUPPLY_SUPPLIER",
            resource_id=row.id,
            detail={"party_id": row.party_id, "code": row.code},
        )
        self._commit("SUPPLIER_CONFLICT", "供应商编码或企业主体已存在")
        return self._supplier_dict(row)

    def change_supplier_status(self, supplier_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("supplier:manage")
        row = self.repo.supplier(supplier_id, for_update=True)
        if row is None:
            raise AppError("供应商不存在", code="SUPPLIER_NOT_FOUND", status_code=404)
        require_version(row.lock_version, data["expected_version"])
        status = str(data["status"])
        if status not in {"ACTIVE", "SUSPENDED", "RETIRED"}:
            raise AppError("供应商状态无效", code="VALIDATION_ERROR", status_code=400)
        row.status, row.lock_version = status, int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="status",
            resource_type="SUPPLY_SUPPLIER",
            resource_id=row.id,
            detail={"status": status, "reason": data.get("reason")},
        )
        self._commit("SUPPLIER_CONFLICT", "供应商状态冲突")
        return self.supplier_detail(row.id)

    def add_supplier_scope(self, supplier_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("supplier:manage")
        supplier = self.repo.supplier(supplier_id)
        if supplier is None:
            raise AppError("供应商不存在", code="SUPPLIER_NOT_FOUND", status_code=404)
        park_id = self._park(data["park_id"])
        row = self.repo.create_scope(
            supplier_id=supplier.id,
            park_id=park_id,
            service_type=normalize_code(
                data.get("service_type") or "GENERAL", field="service_type"
            ),
            status="ACTIVE",
        )
        self.audit.record(
            action="scope",
            resource_type="SUPPLY_SUPPLIER",
            resource_id=supplier.id,
            park_id=park_id,
            detail={"scope_id": row.id, "service_type": row.service_type},
        )
        self._commit("SUPPLIER_SCOPE_CONFLICT", "供应商园区服务范围已存在")
        return self.supplier_detail(supplier.id)

    def add_qualification(self, supplier_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("supplier:credential")
        supplier = self.repo.supplier(supplier_id)
        if supplier is None:
            raise AppError("供应商不存在", code="SUPPLIER_NOT_FOUND", status_code=404)
        attachment_id = int(data["attachment_id"]) if data.get("attachment_id") else None
        if attachment_id and self.repo.attachment(attachment_id) is None:
            raise AppError("资质附件不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
        masked, fingerprint = credential_projection(
            data["credential_number"], secret=self._fingerprint_secret
        )
        effective_on, expires_on = data["effective_on"], data.get("expires_on")
        if expires_on is not None and expires_on < effective_on:
            raise AppError("资质到期日早于生效日", code="VALIDATION_ERROR", status_code=400)
        row = self.repo.create_qualification(
            supplier_id=supplier.id,
            qualification_type=normalize_code(
                data["qualification_type"], field="qualification_type"
            ),
            credential_masked=masked,
            credential_fingerprint=fingerprint,
            issuer=clean_text(data["issuer"], field="issuer", maximum=128),
            effective_on=effective_on,
            expires_on=expires_on,
            status="ACTIVE",
            attachment_id=attachment_id,
        )
        self.audit.record(
            action="qualification",
            resource_type="SUPPLY_SUPPLIER",
            resource_id=supplier.id,
            detail={
                "qualification_id": row.id,
                "qualification_type": row.qualification_type,
                "credential_masked": masked,
            },
        )
        self._commit("SUPPLIER_QUALIFICATION_CONFLICT", "供应商资质已存在")
        return self.supplier_detail(supplier.id)

    def add_evaluation(self, supplier_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("supplier:manage", "outsourcing:accept")
        supplier = self.repo.supplier(supplier_id)
        if supplier is None:
            raise AppError("供应商不存在", code="SUPPLIER_NOT_FOUND", status_code=404)
        park_id = self._park(data["park_id"])
        row = self.repo.create_evaluation(
            park_id=park_id,
            supplier_id=supplier.id,
            source_type=normalize_code(data["source_type"], field="source_type"),
            source_id=int(data["source_id"]),
            score=int(data["score"]),
            comment=clean_text(data.get("comment"), field="comment", maximum=1000, required=False)
            or None,
            evaluated_by=self.ctx.user_id or None,
            evaluated_at=utc_now(),
        )
        self.audit.record(
            action="evaluate",
            resource_type="SUPPLY_SUPPLIER",
            resource_id=supplier.id,
            park_id=park_id,
            detail={"evaluation_id": row.id, "score": row.score},
        )
        self._commit("SUPPLIER_EVALUATION_CONFLICT", "供应商评价写入冲突")
        return self.supplier_detail(supplier.id)

    def list_materials(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None,
        keyword: str | None,
    ) -> list[dict[str, Any]]:
        self._permission("supply:read")
        normalized_keyword = (
            clean_text(keyword, field="keyword", maximum=100, required=False) or None
        )
        return [
            self._material_dict(row)
            for row in self.repo.list_materials(
                status=status,
                keyword=normalized_keyword,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
        ]

    def create_material(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("inventory:manage")
        row = self.repo.create_material(
            code=normalize_code(data["code"]),
            name=clean_text(data["name"], field="name", maximum=128),
            category=clean_text(data["category"], field="category", maximum=64),
            unit=clean_text(data["unit"], field="unit", maximum=16),
            reorder_point=nonnegative_decimal(data.get("reorder_point", 0), field="reorder_point"),
            status="ACTIVE",
        )
        self.audit.record(
            action="create",
            resource_type="SUPPLY_MATERIAL",
            resource_id=row.id,
            detail={"code": row.code},
        )
        self._commit("MATERIAL_CONFLICT", "物料编码已存在")
        return self._material_dict(row)

    def list_warehouses(
        self,
        park_id: int | None,
        *,
        page: int,
        page_size: int,
        status: str | None,
        keyword: str | None,
    ) -> list[dict[str, Any]]:
        self._permission("supply:read")
        if park_id is not None:
            self._park(park_id)
        normalized_keyword = (
            clean_text(keyword, field="keyword", maximum=100, required=False) or None
        )
        return [
            self._warehouse_dict(row)
            for row in self.repo.list_warehouses(
                park_id,
                status=status,
                keyword=normalized_keyword,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
        ]

    def create_warehouse(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("inventory:manage")
        park_id = self._park(data["park_id"])
        row = self.repo.create_warehouse(
            park_id=park_id,
            code=normalize_code(data["code"]),
            name=clean_text(data["name"], field="name", maximum=128),
            status="ACTIVE",
        )
        self.audit.record(
            action="create",
            resource_type="SUPPLY_WAREHOUSE",
            resource_id=row.id,
            park_id=park_id,
            detail={"code": row.code},
        )
        self._commit("WAREHOUSE_CONFLICT", "仓库编码已存在")
        return self._warehouse_dict(row)

    def list_balances(self, park_id: int | None, warehouse_id: int | None) -> list[dict[str, Any]]:
        self._permission("supply:read")
        if park_id is not None:
            self._park(park_id)
        if warehouse_id is not None and self.repo.warehouse(warehouse_id) is None:
            raise AppError("仓库不存在", code="WAREHOUSE_NOT_FOUND", status_code=404)
        return [
            self._balance_dict(row)
            for row in self.repo.balances(park_id=park_id, warehouse_id=warehouse_id)
        ]

    def list_movements(self, balance_id: int | None, limit: int) -> list[dict[str, Any]]:
        self._permission("supply:read")
        return [
            self._movement_dict(row)
            for row in self.repo.movements(balance_id=balance_id, limit=limit)
        ]

    def _requisition_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        approval = self.repo.approval(row.approval_id)
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "request_no": row.request_no,
            "purpose": row.purpose,
            "status": row.status,
            "approval_id": row.approval_id,
            "approval_status": approval.status if approval else None,
            "lock_version": int(row.lock_version),
            "lines": [
                {
                    "id": int(line.id),
                    "line_no": int(line.line_no),
                    "material_id": int(line.material_id),
                    "quantity": str(line.quantity),
                    "estimated_unit_price": str(line.estimated_unit_price),
                    "purpose": line.purpose,
                }
                for line in self.repo.requisition_lines(row.id)
            ],
        }

    def list_requisitions(self) -> list[dict[str, Any]]:
        self._permission("supply:read", "procurement:request")
        return [self._requisition_dict(row) for row in self.repo.list_requisitions()]

    def create_requisition(self, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("procurement:request")
        park_id = self._park(data["park_id"])
        lines = []
        for index, item in enumerate(data["lines"], 1):
            material = self.repo.material(int(item["material_id"]))
            if material is None or material.status != "ACTIVE":
                raise AppError("物料不存在", code="MATERIAL_NOT_FOUND", status_code=404)
            lines.append(
                {
                    "line_no": index,
                    "material_id": int(material.id),
                    "quantity": str(positive_decimal(item["quantity"], field="quantity")),
                    "estimated_unit_price": str(
                        nonnegative_decimal(
                            item.get("estimated_unit_price", 0), field="estimated_unit_price"
                        )
                    ),
                    "purpose": clean_text(
                        item.get("purpose"), field="line purpose", maximum=255, required=False
                    )
                    or None,
                }
            )
        canonical = {
            "park_id": park_id,
            "purpose": clean_text(data["purpose"], field="purpose", maximum=500),
            "lines": lines,
        }
        digest = canonical_hash(canonical)
        previous = self.repo.requisition_by_key(key)
        if previous is not None:
            if previous.payload_hash != digest:
                raise AppError(
                    "幂等键已用于其他采购申请", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._requisition_dict(previous)
        row = self.repo.create_requisition(
            park_id=park_id,
            request_no=self._number("PR", key),
            purpose=canonical["purpose"],
            status="DRAFT",
            idempotency_key=key,
            payload_hash=digest,
            lock_version=1,
            requested_by=self.ctx.user_id or None,
        )
        for line in lines:
            self.repo.create_requisition_line(requisition_id=row.id, **line)
        self.audit.record(
            action="create",
            resource_type="PROCUREMENT_REQUISITION",
            resource_id=row.id,
            park_id=park_id,
            detail={"request_no": row.request_no, "line_count": len(lines)},
        )
        self._commit("PROCUREMENT_REQUISITION_CONFLICT", "采购申请冲突")
        return self._requisition_dict(row)

    def submit_requisition(
        self, requisition_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("procurement:request")
        row = self.repo.requisition(requisition_id, for_update=True)
        if row is None:
            raise AppError(
                "采购申请不存在", code="PROCUREMENT_REQUISITION_NOT_FOUND", status_code=404
            )
        require_version(row.lock_version, data["expected_version"])
        if row.status != "DRAFT":
            if row.status == "PENDING_APPROVAL" and row.approval_id:
                return self._requisition_dict(row)
            raise AppError(
                "采购申请状态不可提交", code="PROCUREMENT_STATE_INVALID", status_code=409
            )
        snapshot = self._requisition_dict(row)
        approval = self.approvals.create(
            {
                "biz_type": "PROCUREMENT_REQUISITION",
                "biz_id": str(row.id),
                "title": f"采购申请：{row.request_no}",
                "park_id": row.park_id,
                "definition_code": normalize_identifier(
                    data["definition_code"], field="definition_code"
                ),
                "idempotency_key": f"supply-procurement:{key}",
                "priority": data.get("priority", "MEDIUM"),
                "snapshot": snapshot,
            }
        )
        row.status, row.approval_id, row.submitted_at, row.lock_version = (
            "PENDING_APPROVAL",
            int(approval["id"]),
            utc_now(),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self.audit.record(
            action="submit",
            resource_type="PROCUREMENT_REQUISITION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"approval_id": row.approval_id},
        )
        self._commit("PROCUREMENT_REQUISITION_CONFLICT", "采购申请提交冲突")
        return self._requisition_dict(row)

    def update_requisition_draft(self, requisition_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("procurement:request")
        row = self.repo.requisition(requisition_id, for_update=True)
        if row is None:
            raise AppError(
                "采购申请不存在", code="PROCUREMENT_REQUISITION_NOT_FOUND", status_code=404
            )
        require_version(row.lock_version, data["expected_version"])
        if row.status != "DRAFT":
            raise AppError(
                "仅草稿采购申请可编辑", code="PROCUREMENT_STATE_INVALID", status_code=409
            )
        park_id = self._park(data["park_id"])
        lines: list[dict[str, Any]] = []
        material_ids: set[int] = set()
        for item in data["lines"]:
            material_id = int(item["material_id"])
            material = self.repo.material(material_id)
            if material is None or material.status != "ACTIVE":
                raise AppError("物料不存在", code="MATERIAL_NOT_FOUND", status_code=404)
            if material_id in material_ids:
                raise AppError("采购物料重复", code="VALIDATION_ERROR", status_code=400)
            material_ids.add(material_id)
            lines.append(
                {
                    "material_id": material_id,
                    "quantity": positive_decimal(item["quantity"], field="quantity"),
                    "estimated_unit_price": nonnegative_decimal(
                        item.get("estimated_unit_price", 0), field="estimated_unit_price"
                    ),
                    "purpose": clean_text(
                        item.get("purpose"), field="purpose", maximum=255, required=False
                    )
                    or None,
                }
            )
        self.repo.delete_requisition_lines(row.id)
        row.park_id = park_id
        row.purpose = clean_text(data["purpose"], field="purpose", maximum=500)
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        for index, line in enumerate(lines, 1):
            self.repo.create_requisition_line(
                requisition_id=row.id,
                line_no=index,
                **line,
            )
        self.audit.record(
            action="update_draft",
            resource_type="PROCUREMENT_REQUISITION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"line_count": len(lines), "expected_version": data["expected_version"]},
        )
        self._commit("PROCUREMENT_REQUISITION_CONFLICT", "采购申请草稿更新冲突")
        return self._requisition_dict(row)

    def sync_requisition(self, requisition_id: int) -> dict[str, Any]:
        self._permission("procurement:request", "procurement:approve")
        row = self.repo.requisition(requisition_id, for_update=True)
        if row is None:
            raise AppError(
                "采购申请不存在", code="PROCUREMENT_REQUISITION_NOT_FOUND", status_code=404
            )
        approval = self.repo.approval(row.approval_id)
        if approval is None:
            raise AppError("审批关联缺失", code="APPROVAL_LINK_MISSING", status_code=409)
        target = approval_state(approval.status)
        if target != row.status:
            row.status, row.lock_version = target, int(row.lock_version) + 1
            self.repo.save(row)
            self.audit.record(
                action="reconcile_approval",
                resource_type="PROCUREMENT_REQUISITION",
                resource_id=row.id,
                park_id=row.park_id,
                detail={"approval_status": approval.status, "status": target},
            )
            self._commit("PROCUREMENT_REQUISITION_CONFLICT", "采购申请同步冲突")
        return self._requisition_dict(row)

    def cancel_requisition(
        self, requisition_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("procurement:request")
        row = self.repo.requisition(requisition_id, for_update=True)
        if row is None:
            raise AppError(
                "采购申请不存在", code="PROCUREMENT_REQUISITION_NOT_FOUND", status_code=404
            )
        if row.status == "CANCELLED":
            return self._requisition_dict(row)
        require_version(row.lock_version, data["expected_version"])
        if row.status not in {"DRAFT", "PENDING_APPROVAL"}:
            raise AppError(
                "采购申请状态不可取消", code="PROCUREMENT_STATE_INVALID", status_code=409
            )
        reason = clean_text(data["reason"], field="reason", maximum=500)
        if row.status == "PENDING_APPROVAL":
            approval = self.repo.approval(row.approval_id)
            if approval is None:
                raise AppError("审批关联缺失", code="APPROVAL_LINK_MISSING", status_code=409)
            self.approvals.withdraw(
                int(approval.id),
                remark=reason,
                expected_version=int(approval.lock_version),
                idempotency_key=f"supply-procurement-cancel:{key}",
            )
        row.status, row.lock_version = "CANCELLED", int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="cancel",
            resource_type="PROCUREMENT_REQUISITION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"reason": reason, "approval_id": row.approval_id},
        )
        self._commit("PROCUREMENT_REQUISITION_CONFLICT", "采购申请取消冲突")
        return self._requisition_dict(row)

    def _order_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "requisition_id": int(row.requisition_id),
            "supplier_id": int(row.supplier_id),
            "order_no": row.order_no,
            "status": row.status,
            "truth_mode": row.truth_mode,
            "currency": row.currency,
            "total_amount": str(row.total_amount),
            "lock_version": int(row.lock_version),
            "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
            "lines": [
                {
                    "id": int(line.id),
                    "line_no": int(line.line_no),
                    "material_id": int(line.material_id),
                    "ordered_qty": str(line.ordered_qty),
                    "received_qty": str(line.received_qty),
                    "unit_price": str(line.unit_price),
                }
                for line in self.repo.order_lines(row.id)
            ],
        }

    def list_orders(self) -> list[dict[str, Any]]:
        self._permission("supply:read", "procurement:order")
        return [self._order_dict(row) for row in self.repo.list_orders()]

    def create_order(self, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("procurement:order")
        requisition = self.repo.requisition(int(data["requisition_id"]), for_update=True)
        if requisition is None:
            raise AppError(
                "采购申请不存在", code="PROCUREMENT_REQUISITION_NOT_FOUND", status_code=404
            )
        if requisition.status != "APPROVED":
            raise AppError("采购申请未获批准", code="PROCUREMENT_NOT_APPROVED", status_code=409)
        supplier_id = int(data["supplier_id"])
        if not self.repo.supplier_eligible(
            supplier_id, requisition.park_id, "PROCUREMENT", data.get("required_qualification")
        ):
            raise AppError(
                "供应商不满足园区范围或资质要求", code="SUPPLIER_NOT_ELIGIBLE", status_code=409
            )
        prices = {
            int(item["requisition_line_id"]): nonnegative_decimal(
                item["unit_price"], field="unit_price"
            )
            for item in data["lines"]
        }
        request_lines = self.repo.requisition_lines(requisition.id)
        if set(prices) != {int(line.id) for line in request_lines}:
            raise AppError(
                "订单行必须完整对应采购申请", code="PURCHASE_ORDER_LINES_INVALID", status_code=400
            )
        truth_mode = str(data.get("truth_mode") or "LOCAL")
        if truth_mode not in {"LOCAL", "EXTERNAL_PENDING"}:
            raise AppError("订单真值模式无效", code="VALIDATION_ERROR", status_code=400)
        row = self.repo.create_order(
            park_id=requisition.park_id,
            requisition_id=requisition.id,
            supplier_id=supplier_id,
            order_no=self._number("PO", key),
            status="ACK_PENDING" if truth_mode == "EXTERNAL_PENDING" else "ISSUED",
            truth_mode=truth_mode,
            currency=str(data.get("currency") or "CNY").upper(),
            total_amount=sum(
                (Decimal(line.quantity) * prices[int(line.id)] for line in request_lines),
                Decimal(0),
            ),
            lock_version=1,
            ordered_by=self.ctx.user_id or None,
        )
        for index, line in enumerate(request_lines, 1):
            self.repo.create_order_line(
                order_id=row.id,
                requisition_line_id=line.id,
                line_no=index,
                material_id=line.material_id,
                ordered_qty=line.quantity,
                unit_price=prices[int(line.id)],
                received_qty=Decimal(0),
            )
        requisition.status, requisition.lock_version = "ORDERED", int(requisition.lock_version) + 1
        self.repo.save(requisition)
        self.audit.record(
            action="create",
            resource_type="PURCHASE_ORDER",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"order_no": row.order_no, "truth_mode": truth_mode, "supplier_id": supplier_id},
        )
        self._commit("PURCHASE_ORDER_CONFLICT", "采购订单冲突")
        return self._order_dict(row)

    def acknowledge_order(self, order_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("procurement:order")
        row = self.repo.order(order_id, for_update=True)
        if row is None:
            raise AppError("采购订单不存在", code="PURCHASE_ORDER_NOT_FOUND", status_code=404)
        require_version(row.lock_version, data["expected_version"])
        if row.status not in {"ISSUED", "ACK_PENDING"}:
            raise AppError("订单状态不可确认", code="PURCHASE_ORDER_STATE_INVALID", status_code=409)
        accepted = bool(data["accepted"])
        row.status = "ACKNOWLEDGED" if accepted else "REJECTED"
        row.acknowledged_at, row.lock_version = utc_now(), int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="acknowledge",
            resource_type="PURCHASE_ORDER",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"accepted": accepted, "reason": data.get("reason")},
        )
        self._commit("PURCHASE_ORDER_CONFLICT", "采购订单确认冲突")
        return self._order_dict(row)

    def _receipt_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "order_id": int(row.order_id),
            "warehouse_id": int(row.warehouse_id),
            "receipt_no": row.receipt_no,
            "status": row.status,
            "received_at": row.received_at.isoformat(),
            "lines": [
                {
                    "id": int(line.id),
                    "order_line_id": int(line.order_line_id),
                    "quantity": str(line.quantity),
                    "batch_no": line.batch_no,
                    "movement_id": int(line.movement_id),
                }
                for line in self.repo.receipt_lines(row.id)
            ],
        }

    def receive_order(self, order_id: int, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("inventory:manage", "procurement:order")
        canonical = {
            "order_id": order_id,
            "warehouse_id": int(data["warehouse_id"]),
            "lines": sorted(
                [
                    {
                        "order_line_id": int(item["order_line_id"]),
                        "quantity": str(positive_decimal(item["quantity"], field="quantity")),
                        "batch_no": clean_text(
                            item.get("batch_no"), field="batch_no", maximum=64, required=False
                        )
                        or None,
                    }
                    for item in data["lines"]
                ],
                key=lambda item: item["order_line_id"],
            ),
        }
        digest = canonical_hash(canonical)
        previous = self.repo.receipt_by_key(key)
        if previous is not None:
            if previous.payload_hash != digest:
                raise AppError("幂等键已用于其他收货", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._receipt_dict(previous)
        order = self.repo.order(order_id, for_update=True)
        if order is None:
            raise AppError("采购订单不存在", code="PURCHASE_ORDER_NOT_FOUND", status_code=404)
        if (
            order.status not in {"ISSUED", "ACKNOWLEDGED", "PARTIALLY_RECEIVED"}
            or order.truth_mode != "LOCAL"
        ):
            raise AppError(
                "订单当前不可本地收货", code="PURCHASE_ORDER_STATE_INVALID", status_code=409
            )
        warehouse = self.repo.warehouse(canonical["warehouse_id"])
        if (
            warehouse is None
            or int(warehouse.park_id) != int(order.park_id)
            or warehouse.status != "ACTIVE"
        ):
            raise AppError("收货仓库不存在", code="WAREHOUSE_NOT_FOUND", status_code=404)
        order_lines = {
            int(line.id): line for line in self.repo.order_lines(order.id, for_update=True)
        }
        if not canonical["lines"] or any(
            item["order_line_id"] not in order_lines for item in canonical["lines"]
        ):
            raise AppError("收货行不属于该订单", code="RECEIPT_LINES_INVALID", status_code=400)
        receipt = self.repo.create_receipt(
            park_id=order.park_id,
            order_id=order.id,
            warehouse_id=warehouse.id,
            receipt_no=self._number("GR", key),
            status="POSTED",
            idempotency_key=key,
            payload_hash=digest,
            received_by=self.ctx.user_id or None,
            received_at=utc_now(),
        )
        for item in canonical["lines"]:
            line = order_lines[item["order_line_id"]]
            quantity = Decimal(item["quantity"])
            if Decimal(line.received_qty) + quantity > Decimal(line.ordered_qty):
                raise AppError("收货数量超过订单剩余数量", code="OVER_RECEIPT", status_code=409)
            balance = self.repo.balance(
                park_id=order.park_id,
                warehouse_id=warehouse.id,
                material_id=line.material_id,
                for_update=True,
            )
            if balance is None:
                balance = self.repo.create_balance(
                    park_id=order.park_id,
                    warehouse_id=warehouse.id,
                    material_id=line.material_id,
                    on_hand_qty=Decimal(0),
                    reserved_qty=Decimal(0),
                    lock_version=1,
                )
            movement = self.repo.create_movement(
                park_id=order.park_id,
                balance_id=balance.id,
                warehouse_id=warehouse.id,
                material_id=line.material_id,
                movement_type="RECEIPT",
                quantity=quantity,
                reference_type="GOODS_RECEIPT",
                reference_id=receipt.id,
                reverses_movement_id=None,
                idempotency_key=f"receipt:{key}:{line.id}",
                payload_hash=canonical_hash(item),
                actor_user_id=self.ctx.user_id or None,
                occurred_at=utc_now(),
            )
            balance.on_hand_qty, balance.lock_version = (
                Decimal(balance.on_hand_qty) + quantity,
                int(balance.lock_version) + 1,
            )
            line.received_qty = Decimal(line.received_qty) + quantity
            self.repo.save(balance)
            self.repo.save(line)
            self.repo.create_receipt_line(
                receipt_id=receipt.id,
                order_line_id=line.id,
                quantity=quantity,
                batch_no=item["batch_no"],
                movement_id=movement.id,
            )
        complete = all(
            Decimal(line.received_qty) == Decimal(line.ordered_qty) for line in order_lines.values()
        )
        order.status, order.lock_version = (
            ("RECEIVED" if complete else "PARTIALLY_RECEIVED"),
            int(order.lock_version) + 1,
        )
        self.repo.save(order)
        self.audit.record(
            action="receipt",
            resource_type="PURCHASE_ORDER",
            resource_id=order.id,
            park_id=order.park_id,
            detail={"receipt_id": receipt.id, "line_count": len(canonical["lines"])},
        )
        self._commit("GOODS_RECEIPT_CONFLICT", "收货并发冲突")
        return self._receipt_dict(receipt)

    def _inventory_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        approval = self.repo.approval(row.approval_id)
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "request_no": row.request_no,
            "purpose": row.purpose,
            "work_order_id": row.work_order_id,
            "status": row.status,
            "approval_id": row.approval_id,
            "approval_status": approval.status if approval else None,
            "lock_version": int(row.lock_version),
            "lines": [
                {
                    "id": int(line.id),
                    "line_no": int(line.line_no),
                    "warehouse_id": int(line.warehouse_id),
                    "material_id": int(line.material_id),
                    "requested_qty": str(line.requested_qty),
                    "reserved_qty": str(line.reserved_qty),
                    "issued_qty": str(line.issued_qty),
                    "returned_qty": str(line.returned_qty),
                }
                for line in self.repo.inventory_lines(row.id)
            ],
        }

    def list_inventory(self) -> list[dict[str, Any]]:
        self._permission("supply:read", "inventory:issue")
        return [self._inventory_dict(row) for row in self.repo.list_inventory()]

    def create_inventory_requisition(self, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("inventory:issue")
        park_id = self._park(data["park_id"])
        work_order_id = int(data["work_order_id"]) if data.get("work_order_id") else None
        if work_order_id and self.repo.work_order(work_order_id, park_id) is None:
            raise AppError("关联工单不存在", code="WORK_ORDER_NOT_FOUND", status_code=404)
        lines = []
        for index, item in enumerate(data["lines"], 1):
            warehouse = self.repo.warehouse(int(item["warehouse_id"]))
            material = self.repo.material(int(item["material_id"]))
            if warehouse is None or int(warehouse.park_id) != park_id:
                raise AppError("仓库不存在", code="WAREHOUSE_NOT_FOUND", status_code=404)
            if material is None or material.status != "ACTIVE":
                raise AppError("物料不存在", code="MATERIAL_NOT_FOUND", status_code=404)
            lines.append(
                {
                    "line_no": index,
                    "warehouse_id": int(warehouse.id),
                    "material_id": int(material.id),
                    "requested_qty": str(positive_decimal(item["quantity"], field="quantity")),
                }
            )
        canonical = {
            "park_id": park_id,
            "purpose": clean_text(data["purpose"], field="purpose", maximum=500),
            "work_order_id": work_order_id,
            "lines": lines,
        }
        digest = canonical_hash(canonical)
        previous = self.repo.inventory_by_key(key)
        if previous is not None:
            if previous.payload_hash != digest:
                raise AppError(
                    "幂等键已用于其他领用申请", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._inventory_dict(previous)
        row = self.repo.create_inventory(
            park_id=park_id,
            request_no=self._number("IR", key),
            purpose=canonical["purpose"],
            work_order_id=work_order_id,
            status="DRAFT",
            approval_id=None,
            idempotency_key=key,
            payload_hash=digest,
            lock_version=1,
            requested_by=self.ctx.user_id or None,
        )
        for line in lines:
            self.repo.create_inventory_line(
                park_id=park_id,
                requisition_id=row.id,
                reserved_qty=Decimal(0),
                issued_qty=Decimal(0),
                returned_qty=Decimal(0),
                **line,
            )
        self.audit.record(
            action="create",
            resource_type="INVENTORY_REQUISITION",
            resource_id=row.id,
            park_id=park_id,
            detail={"work_order_id": work_order_id, "line_count": len(lines)},
        )
        self._commit("INVENTORY_REQUISITION_CONFLICT", "领用申请冲突")
        return self._inventory_dict(row)

    def submit_inventory_requisition(
        self, requisition_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("inventory:issue")
        row = self.repo.inventory(requisition_id, for_update=True)
        if row is None:
            raise AppError(
                "领用申请不存在", code="INVENTORY_REQUISITION_NOT_FOUND", status_code=404
            )
        require_version(row.lock_version, data["expected_version"])
        if row.status != "DRAFT":
            if row.status == "PENDING_APPROVAL":
                return self._inventory_dict(row)
            raise AppError("领用申请状态不可提交", code="INVENTORY_STATE_INVALID", status_code=409)
        approval = self.approvals.create(
            {
                "biz_type": "INVENTORY_REQUISITION",
                "biz_id": str(row.id),
                "title": f"物料领用：{row.request_no}",
                "park_id": row.park_id,
                "definition_code": normalize_identifier(
                    data["definition_code"], field="definition_code"
                ),
                "idempotency_key": f"supply-inventory:{key}",
                "priority": data.get("priority", "MEDIUM"),
                "snapshot": self._inventory_dict(row),
            }
        )
        row.status, row.approval_id, row.lock_version = (
            "PENDING_APPROVAL",
            int(approval["id"]),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self.audit.record(
            action="submit",
            resource_type="INVENTORY_REQUISITION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"approval_id": row.approval_id},
        )
        self._commit("INVENTORY_REQUISITION_CONFLICT", "领用申请提交冲突")
        return self._inventory_dict(row)

    def sync_inventory_requisition(self, requisition_id: int) -> dict[str, Any]:
        self._permission("inventory:issue", "procurement:approve")
        row = self.repo.inventory(requisition_id, for_update=True)
        if row is None:
            raise AppError(
                "领用申请不存在", code="INVENTORY_REQUISITION_NOT_FOUND", status_code=404
            )
        approval = self.repo.approval(row.approval_id)
        if approval is None:
            raise AppError("审批关联缺失", code="APPROVAL_LINK_MISSING", status_code=409)
        target = approval_state(approval.status)
        if target == "APPROVED" and row.status != "APPROVED":
            balances = []
            for line in self.repo.inventory_lines(row.id, for_update=True):
                balance = self.repo.balance(
                    park_id=row.park_id,
                    warehouse_id=line.warehouse_id,
                    material_id=line.material_id,
                    for_update=True,
                )
                requested = Decimal(line.requested_qty)
                if (
                    balance is None
                    or Decimal(balance.on_hand_qty) - Decimal(balance.reserved_qty) < requested
                ):
                    raise AppError(
                        "可用库存不足，无法批准预留", code="INSUFFICIENT_STOCK", status_code=409
                    )
                balances.append((line, balance, requested))
            for line, balance, requested in balances:
                balance.reserved_qty, balance.lock_version = (
                    Decimal(balance.reserved_qty) + requested,
                    int(balance.lock_version) + 1,
                )
                line.reserved_qty = requested
                self.repo.save(balance)
                self.repo.save(line)
            row.status = "APPROVED"
        elif target != row.status and target != "APPROVED":
            row.status = target
        else:
            return self._inventory_dict(row)
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="reconcile_approval",
            resource_type="INVENTORY_REQUISITION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"approval_status": approval.status, "status": row.status},
        )
        self._commit("INVENTORY_REQUISITION_CONFLICT", "领用预留并发冲突")
        return self._inventory_dict(row)

    def issue_inventory(
        self, requisition_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("inventory:issue")
        canonical = {
            "requisition_id": requisition_id,
            "lines": sorted(
                [
                    {
                        "line_id": int(item["line_id"]),
                        "quantity": str(positive_decimal(item["quantity"], field="quantity")),
                    }
                    for item in data["lines"]
                ],
                key=lambda item: item["line_id"],
            ),
        }
        digest = canonical_hash(canonical)
        existing = [
            self.repo.movement_by_key(f"issue:{key}:{item['line_id']}")
            for item in canonical["lines"]
        ]
        if any(existing):
            if not all(existing) or any(item.payload_hash != digest for item in existing if item):
                raise AppError("幂等键已用于其他发料", code="IDEMPOTENCY_CONFLICT", status_code=409)
            row = self.repo.inventory(requisition_id)
            if row is None:
                raise AppError(
                    "领用申请不存在", code="INVENTORY_REQUISITION_NOT_FOUND", status_code=404
                )
            return self._inventory_dict(row)
        row = self.repo.inventory(requisition_id, for_update=True)
        if row is None:
            raise AppError(
                "领用申请不存在", code="INVENTORY_REQUISITION_NOT_FOUND", status_code=404
            )
        if row.status not in {"APPROVED", "PARTIALLY_ISSUED"}:
            raise AppError(
                "领用申请未批准或已完成", code="INVENTORY_STATE_INVALID", status_code=409
            )
        lines = {int(line.id): line for line in self.repo.inventory_lines(row.id, for_update=True)}
        if not canonical["lines"] or any(
            item["line_id"] not in lines for item in canonical["lines"]
        ):
            raise AppError("发料行不属于该申请", code="INVENTORY_LINES_INVALID", status_code=400)
        for item in canonical["lines"]:
            line, quantity = lines[item["line_id"]], Decimal(item["quantity"])
            if Decimal(line.issued_qty) + quantity > Decimal(
                line.requested_qty
            ) or quantity > Decimal(line.reserved_qty):
                raise AppError(
                    "发料数量超过批准剩余数量", code="ISSUE_QUANTITY_INVALID", status_code=409
                )
            balance = self.repo.balance(
                park_id=row.park_id,
                warehouse_id=line.warehouse_id,
                material_id=line.material_id,
                for_update=True,
            )
            if (
                balance is None
                or Decimal(balance.on_hand_qty) < quantity
                or Decimal(balance.reserved_qty) < quantity
            ):
                raise AppError("库存不足或预留已变化", code="INSUFFICIENT_STOCK", status_code=409)
            movement = self.repo.create_movement(
                park_id=row.park_id,
                balance_id=balance.id,
                warehouse_id=line.warehouse_id,
                material_id=line.material_id,
                movement_type="ISSUE",
                quantity=-quantity,
                reference_type="INVENTORY_REQUISITION",
                reference_id=row.id,
                reverses_movement_id=None,
                idempotency_key=f"issue:{key}:{line.id}",
                payload_hash=digest,
                actor_user_id=self.ctx.user_id or None,
                occurred_at=utc_now(),
            )
            balance.on_hand_qty, balance.reserved_qty, balance.lock_version = (
                Decimal(balance.on_hand_qty) - quantity,
                Decimal(balance.reserved_qty) - quantity,
                int(balance.lock_version) + 1,
            )
            line.issued_qty, line.reserved_qty = (
                Decimal(line.issued_qty) + quantity,
                Decimal(line.reserved_qty) - quantity,
            )
            self.repo.save(balance)
            self.repo.save(line)
            self.audit.record(
                action="issue",
                resource_type="STOCK_MOVEMENT",
                resource_id=movement.id,
                park_id=row.park_id,
                detail={"requisition_id": row.id, "line_id": line.id, "quantity": str(quantity)},
            )
        complete = all(
            Decimal(line.issued_qty) == Decimal(line.requested_qty) for line in lines.values()
        )
        row.status, row.lock_version = (
            ("ISSUED" if complete else "PARTIALLY_ISSUED"),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self._commit("INVENTORY_ISSUE_CONFLICT", "发料并发冲突")
        return self._inventory_dict(row)

    def return_inventory(
        self, requisition_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("inventory:issue")
        line_id, quantity = (
            int(data["line_id"]),
            positive_decimal(data["quantity"], field="quantity"),
        )
        canonical = {
            "requisition_id": requisition_id,
            "line_id": line_id,
            "quantity": str(quantity),
        }
        digest, movement_key = canonical_hash(canonical), f"return:{key}:{line_id}"
        previous = self.repo.movement_by_key(movement_key)
        if previous is not None:
            if previous.payload_hash != digest:
                raise AppError("幂等键已用于其他退料", code="IDEMPOTENCY_CONFLICT", status_code=409)
            row = self.repo.inventory(requisition_id)
            if row is None:
                raise AppError(
                    "领用申请不存在", code="INVENTORY_REQUISITION_NOT_FOUND", status_code=404
                )
            return self._inventory_dict(row)
        row = self.repo.inventory(requisition_id, for_update=True)
        if row is None:
            raise AppError(
                "领用申请不存在", code="INVENTORY_REQUISITION_NOT_FOUND", status_code=404
            )
        line = next(
            (
                item
                for item in self.repo.inventory_lines(row.id, for_update=True)
                if int(item.id) == line_id
            ),
            None,
        )
        if line is None:
            raise AppError("领用行不存在", code="INVENTORY_LINE_NOT_FOUND", status_code=404)
        if Decimal(line.returned_qty) + quantity > Decimal(line.issued_qty):
            raise AppError(
                "退料数量超过未退已领数量", code="RETURN_QUANTITY_INVALID", status_code=409
            )
        balance = self.repo.balance(
            park_id=row.park_id,
            warehouse_id=line.warehouse_id,
            material_id=line.material_id,
            for_update=True,
        )
        if balance is None:
            raise AppError("库存余额不存在", code="STOCK_BALANCE_NOT_FOUND", status_code=409)
        movement = self.repo.create_movement(
            park_id=row.park_id,
            balance_id=balance.id,
            warehouse_id=line.warehouse_id,
            material_id=line.material_id,
            movement_type="RETURN",
            quantity=quantity,
            reference_type="INVENTORY_REQUISITION",
            reference_id=row.id,
            reverses_movement_id=None,
            idempotency_key=movement_key,
            payload_hash=digest,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        balance.on_hand_qty, balance.lock_version = (
            Decimal(balance.on_hand_qty) + quantity,
            int(balance.lock_version) + 1,
        )
        line.returned_qty = Decimal(line.returned_qty) + quantity
        self.repo.save(balance)
        self.repo.save(line)
        self.audit.record(
            action="return",
            resource_type="STOCK_MOVEMENT",
            resource_id=movement.id,
            park_id=row.park_id,
            detail={"requisition_id": row.id, "quantity": str(quantity)},
        )
        self._commit("INVENTORY_RETURN_CONFLICT", "退料并发冲突")
        return self._inventory_dict(row)

    def _stocktake_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        approval = self.repo.approval(row.approval_id)
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "warehouse_id": int(row.warehouse_id),
            "stocktake_no": row.stocktake_no,
            "status": row.status,
            "approval_id": row.approval_id,
            "approval_status": approval.status if approval else None,
            "lock_version": int(row.lock_version),
            "lines": [
                {
                    "id": int(line.id),
                    "material_id": int(line.material_id),
                    "expected_qty": str(line.expected_qty),
                    "counted_qty": str(line.counted_qty),
                    "variance_qty": str(Decimal(line.counted_qty) - Decimal(line.expected_qty)),
                    "adjustment_movement_id": line.adjustment_movement_id,
                }
                for line in self.repo.stocktake_lines(row.id)
            ],
        }

    def list_stocktakes(self) -> list[dict[str, Any]]:
        self._permission("supply:read")
        return [self._stocktake_dict(row) for row in self.repo.list_stocktakes()]

    def create_stocktake(self, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("inventory:adjust")
        warehouse = self.repo.warehouse(int(data["warehouse_id"]))
        if warehouse is None or warehouse.status != "ACTIVE":
            raise AppError("仓库不存在", code="WAREHOUSE_NOT_FOUND", status_code=404)
        counts = {
            int(item["material_id"]): nonnegative_decimal(item["counted_qty"], field="counted_qty")
            for item in data["lines"]
        }
        canonical = {
            "warehouse_id": int(warehouse.id),
            "lines": sorted(
                [
                    {"material_id": key_id, "counted_qty": str(value)}
                    for key_id, value in counts.items()
                ],
                key=lambda item: item["material_id"],
            ),
        }
        digest = canonical_hash(canonical)
        previous = self.repo.stocktake_by_key(key)
        if previous is not None:
            if previous.payload_hash != digest:
                raise AppError("幂等键已用于其他盘点", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._stocktake_dict(previous)
        row = self.repo.create_stocktake(
            park_id=warehouse.park_id,
            warehouse_id=warehouse.id,
            stocktake_no=self._number("ST", key),
            status="DRAFT",
            approval_id=None,
            idempotency_key=key,
            payload_hash=digest,
            lock_version=1,
            counted_by=self.ctx.user_id or None,
        )
        for material_id, counted in counts.items():
            material = self.repo.material(material_id)
            if material is None:
                raise AppError("物料不存在", code="MATERIAL_NOT_FOUND", status_code=404)
            balance = self.repo.balance(
                park_id=warehouse.park_id,
                warehouse_id=warehouse.id,
                material_id=material_id,
                for_update=True,
            )
            expected = Decimal(balance.on_hand_qty) if balance else Decimal(0)
            self.repo.create_stocktake_line(
                stocktake_id=row.id,
                material_id=material_id,
                expected_qty=expected,
                counted_qty=counted,
                adjustment_movement_id=None,
            )
        self.audit.record(
            action="create",
            resource_type="STOCKTAKE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"warehouse_id": row.warehouse_id, "line_count": len(counts)},
        )
        self._commit("STOCKTAKE_CONFLICT", "盘点单冲突")
        return self._stocktake_dict(row)

    def submit_stocktake(
        self, stocktake_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("inventory:adjust")
        row = self.repo.stocktake(stocktake_id, for_update=True)
        if row is None:
            raise AppError("盘点单不存在", code="STOCKTAKE_NOT_FOUND", status_code=404)
        require_version(row.lock_version, data["expected_version"])
        if row.status != "DRAFT":
            raise AppError("盘点单状态不可提交", code="STOCKTAKE_STATE_INVALID", status_code=409)
        has_variance = any(
            Decimal(line.counted_qty) != Decimal(line.expected_qty)
            for line in self.repo.stocktake_lines(row.id)
        )
        if has_variance:
            approval = self.approvals.create(
                {
                    "biz_type": "INVENTORY_STOCKTAKE",
                    "biz_id": str(row.id),
                    "title": f"库存盘点差异：{row.stocktake_no}",
                    "park_id": row.park_id,
                    "definition_code": normalize_identifier(
                        data["definition_code"], field="definition_code"
                    ),
                    "idempotency_key": f"supply-stocktake:{key}",
                    "priority": "HIGH",
                    "snapshot": self._stocktake_dict(row),
                }
            )
            row.status, row.approval_id = "PENDING_APPROVAL", int(approval["id"])
        else:
            row.status = "APPROVED"
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="submit",
            resource_type="STOCKTAKE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"approval_id": row.approval_id, "has_variance": has_variance},
        )
        self._commit("STOCKTAKE_CONFLICT", "盘点提交冲突")
        return self._stocktake_dict(row)

    def post_stocktake(self, stocktake_id: int, *, key: str) -> dict[str, Any]:
        self._permission("inventory:adjust")
        row = self.repo.stocktake(stocktake_id, for_update=True)
        if row is None:
            raise AppError("盘点单不存在", code="STOCKTAKE_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if row.status == "PENDING_APPROVAL" and approval and approval.status == "APPROVED":
            row.status = "APPROVED"
        if row.status == "POSTED":
            return self._stocktake_dict(row)
        if row.status != "APPROVED":
            raise AppError("盘点差异尚未批准", code="STOCKTAKE_NOT_APPROVED", status_code=409)
        for line in self.repo.stocktake_lines(row.id):
            variance = Decimal(line.counted_qty) - Decimal(line.expected_qty)
            if variance == 0:
                continue
            movement_key = f"stocktake:{key}:{line.id}"
            previous = self.repo.movement_by_key(movement_key)
            if previous is not None:
                line.adjustment_movement_id = previous.id
                continue
            balance = self.repo.balance(
                park_id=row.park_id,
                warehouse_id=row.warehouse_id,
                material_id=line.material_id,
                for_update=True,
            )
            if balance is None:
                balance = self.repo.create_balance(
                    park_id=row.park_id,
                    warehouse_id=row.warehouse_id,
                    material_id=line.material_id,
                    on_hand_qty=Decimal(0),
                    reserved_qty=Decimal(0),
                    lock_version=1,
                )
            if Decimal(line.counted_qty) < Decimal(balance.reserved_qty):
                raise AppError(
                    "盘点数量低于已预留库存", code="STOCKTAKE_RESERVED_CONFLICT", status_code=409
                )
            movement = self.repo.create_movement(
                park_id=row.park_id,
                balance_id=balance.id,
                warehouse_id=row.warehouse_id,
                material_id=line.material_id,
                movement_type="ADJUSTMENT",
                quantity=variance,
                reference_type="STOCKTAKE",
                reference_id=row.id,
                reverses_movement_id=None,
                idempotency_key=movement_key,
                payload_hash=canonical_hash({"line_id": line.id, "variance": str(variance)}),
                actor_user_id=self.ctx.user_id or None,
                occurred_at=utc_now(),
            )
            balance.on_hand_qty, balance.lock_version = (
                Decimal(balance.on_hand_qty) + variance,
                int(balance.lock_version) + 1,
            )
            line.adjustment_movement_id = movement.id
            self.repo.save(balance)
            self.repo.save(line)
        row.status, row.lock_version = "POSTED", int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="post",
            resource_type="STOCKTAKE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"line_count": len(self.repo.stocktake_lines(row.id))},
        )
        self._commit("STOCKTAKE_CONFLICT", "盘点过账并发冲突")
        return self._stocktake_dict(row)

    def reverse_movement(
        self, movement_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("inventory:adjust")
        original = next(
            (row for row in self.repo.movements(limit=1000) if int(row.id) == int(movement_id)),
            None,
        )
        if original is None:
            raise AppError("库存流水不存在", code="STOCK_MOVEMENT_NOT_FOUND", status_code=404)
        movement_key = f"reversal:{key}:{movement_id}"
        previous = self.repo.movement_by_key(movement_key)
        if previous is not None:
            return self._movement_dict(previous)
        if any(
            int(row.reverses_movement_id or 0) == int(original.id)
            for row in self.repo.movements(balance_id=original.balance_id, limit=1000)
        ):
            raise AppError(
                "库存流水已冲销", code="STOCK_MOVEMENT_ALREADY_REVERSED", status_code=409
            )
        balance = self.repo.balance(
            park_id=original.park_id,
            warehouse_id=original.warehouse_id,
            material_id=original.material_id,
            for_update=True,
        )
        if balance is None or Decimal(balance.on_hand_qty) - Decimal(original.quantity) < Decimal(
            balance.reserved_qty
        ):
            raise AppError("冲销将破坏可用库存", code="STOCK_REVERSAL_CONFLICT", status_code=409)
        reverse_qty = -Decimal(original.quantity)
        row = self.repo.create_movement(
            park_id=original.park_id,
            balance_id=original.balance_id,
            warehouse_id=original.warehouse_id,
            material_id=original.material_id,
            movement_type="REVERSAL",
            quantity=reverse_qty,
            reference_type="STOCK_MOVEMENT",
            reference_id=original.id,
            reverses_movement_id=original.id,
            idempotency_key=movement_key,
            payload_hash=canonical_hash({"movement_id": movement_id, "reason": data["reason"]}),
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        balance.on_hand_qty, balance.lock_version = (
            Decimal(balance.on_hand_qty) + reverse_qty,
            int(balance.lock_version) + 1,
        )
        self.repo.save(balance)
        self.audit.record(
            action="reverse",
            resource_type="STOCK_MOVEMENT",
            resource_id=original.id,
            park_id=original.park_id,
            detail={"reversal_id": row.id, "reason": data["reason"]},
        )
        self._commit("STOCK_REVERSAL_CONFLICT", "库存冲销并发冲突")
        return self._movement_dict(row)

    def _outsourcing_dict(self, row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        approval = self.repo.approval(row.approval_id)
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "supplier_id": int(row.supplier_id),
            "work_order_id": row.work_order_id,
            "order_no": row.order_no,
            "title": row.title,
            "deliverables": row.deliverables_json,
            "sla_due_at": row.sla_due_at.isoformat(),
            "amount": str(row.amount),
            "status": row.status,
            "approval_id": row.approval_id,
            "approval_status": approval.status if approval else None,
            "settlement_state": row.settlement_state,
            "lock_version": int(row.lock_version),
            "events": [
                {
                    "id": int(event.id),
                    "event_type": event.event_type,
                    "note": event.note,
                    "evidence": event.evidence_json,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in self.repo.outsourcing_events(row.id)
            ],
        }

    def list_outsourcing(self) -> list[dict[str, Any]]:
        self._permission("supply:read", "outsourcing:manage")
        return [self._outsourcing_dict(row) for row in self.repo.list_outsourcing()]

    def create_outsourcing(self, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("outsourcing:manage")
        park_id, supplier_id = self._park(data["park_id"]), int(data["supplier_id"])
        if not self.repo.supplier_eligible(
            supplier_id, park_id, "OUTSOURCING", data.get("required_qualification")
        ):
            raise AppError(
                "供应商不满足园区范围或资质要求", code="SUPPLIER_NOT_ELIGIBLE", status_code=409
            )
        work_order_id = int(data["work_order_id"]) if data.get("work_order_id") else None
        if work_order_id and self.repo.work_order(work_order_id, park_id) is None:
            raise AppError("关联工单不存在", code="WORK_ORDER_NOT_FOUND", status_code=404)
        deliverables = [
            {
                "code": normalize_code(item["code"], field="deliverable code"),
                "name": clean_text(item["name"], field="deliverable name", maximum=128),
                "required": bool(item.get("required", True)),
            }
            for item in data["deliverables"]
        ]
        canonical = {
            "park_id": park_id,
            "supplier_id": supplier_id,
            "work_order_id": work_order_id,
            "title": clean_text(data["title"], field="title", maximum=200),
            "deliverables": deliverables,
            "sla_due_at": naive_utc(data["sla_due_at"]).isoformat(),
            "amount": str(nonnegative_decimal(data["amount"], field="amount", scale="0.01")),
        }
        digest = canonical_hash(canonical)
        previous = self.repo.outsourcing_by_key(key)
        if previous is not None:
            if previous.payload_hash != digest:
                raise AppError(
                    "幂等键已用于其他外包单", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            return self._outsourcing_dict(previous)
        row = self.repo.create_outsourcing(
            park_id=park_id,
            supplier_id=supplier_id,
            work_order_id=work_order_id,
            order_no=self._number("OS", key),
            title=canonical["title"],
            deliverables_json=deliverables,
            sla_due_at=naive_utc(data["sla_due_at"]),
            amount=Decimal(canonical["amount"]),
            status="DRAFT",
            approval_id=None,
            settlement_state="NOT_INTEGRATED",
            idempotency_key=key,
            payload_hash=digest,
            lock_version=1,
            requested_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="create",
            resource_type="OUTSOURCING_ORDER",
            resource_id=row.id,
            park_id=park_id,
            detail={
                "supplier_id": supplier_id,
                "work_order_id": work_order_id,
                "settlement_state": "NOT_INTEGRATED",
            },
        )
        self._commit("OUTSOURCING_ORDER_CONFLICT", "外包服务单冲突")
        return self._outsourcing_dict(row)

    def submit_outsourcing(
        self, order_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("outsourcing:manage")
        row = self.repo.outsourcing(order_id, for_update=True)
        if row is None:
            raise AppError("外包服务单不存在", code="OUTSOURCING_ORDER_NOT_FOUND", status_code=404)
        require_version(row.lock_version, data["expected_version"])
        if row.status != "DRAFT":
            if row.status == "PENDING_APPROVAL":
                return self._outsourcing_dict(row)
            raise AppError(
                "外包服务单状态不可提交", code="OUTSOURCING_STATE_INVALID", status_code=409
            )
        if not self.repo.supplier_eligible(
            row.supplier_id, row.park_id, "OUTSOURCING", data.get("required_qualification")
        ):
            raise AppError("供应商资格已失效", code="SUPPLIER_NOT_ELIGIBLE", status_code=409)
        approval = self.approvals.create(
            {
                "biz_type": "OUTSOURCING_ORDER",
                "biz_id": str(row.id),
                "title": f"外包服务：{row.title}",
                "park_id": row.park_id,
                "definition_code": normalize_identifier(
                    data["definition_code"], field="definition_code"
                ),
                "idempotency_key": f"supply-outsourcing:{key}",
                "priority": data.get("priority", "HIGH"),
                "snapshot": self._outsourcing_dict(row),
            }
        )
        row.status, row.approval_id, row.lock_version = (
            "PENDING_APPROVAL",
            int(approval["id"]),
            int(row.lock_version) + 1,
        )
        self.repo.save(row)
        self.repo.create_outsourcing_event(
            park_id=row.park_id,
            order_id=row.id,
            event_type="SUBMITTED",
            note=None,
            evidence_json=None,
            idempotency_key=f"submitted:{key}",
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="submit",
            resource_type="OUTSOURCING_ORDER",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"approval_id": row.approval_id},
        )
        self._commit("OUTSOURCING_ORDER_CONFLICT", "外包服务单提交冲突")
        return self._outsourcing_dict(row)

    def sync_outsourcing(self, order_id: int) -> dict[str, Any]:
        self._permission("outsourcing:manage")
        row = self.repo.outsourcing(order_id, for_update=True)
        if row is None:
            raise AppError("外包服务单不存在", code="OUTSOURCING_ORDER_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if approval is None:
            raise AppError("审批关联缺失", code="APPROVAL_LINK_MISSING", status_code=409)
        target = approval_state(approval.status)
        if target != row.status:
            row.status, row.lock_version = target, int(row.lock_version) + 1
            self.repo.save(row)
            if target == "APPROVED":
                self.repo.create_outsourcing_event(
                    park_id=row.park_id,
                    order_id=row.id,
                    event_type="APPROVED",
                    note=None,
                    evidence_json=None,
                    idempotency_key=f"approval:{row.approval_id}:approved",
                    actor_user_id=self.ctx.user_id or None,
                    occurred_at=utc_now(),
                )
            self.audit.record(
                action="reconcile_approval",
                resource_type="OUTSOURCING_ORDER",
                resource_id=row.id,
                park_id=row.park_id,
                detail={"approval_status": approval.status, "status": target},
            )
            self._commit("OUTSOURCING_ORDER_CONFLICT", "外包审批同步冲突")
        return self._outsourcing_dict(row)

    def outsourcing_event(self, order_id: int, data: dict[str, Any], *, key: str) -> dict[str, Any]:
        self._permission("outsourcing:manage")
        previous = self.repo.event_by_key(key)
        if previous is not None:
            if int(previous.order_id) != int(order_id) or previous.event_type != data["event_type"]:
                raise AppError(
                    "幂等键已用于其他外包事件", code="IDEMPOTENCY_CONFLICT", status_code=409
                )
            row = self.repo.outsourcing(order_id)
            if row is None:
                raise AppError(
                    "外包服务单不存在", code="OUTSOURCING_ORDER_NOT_FOUND", status_code=404
                )
            return self._outsourcing_dict(row)
        row = self.repo.outsourcing(order_id, for_update=True)
        if row is None:
            raise AppError("外包服务单不存在", code="OUTSOURCING_ORDER_NOT_FOUND", status_code=404)
        event_type = str(data["event_type"])
        transitions = {
            "STARTED": ({"APPROVED", "REWORK"}, "IN_PROGRESS"),
            "PROGRESS": ({"IN_PROGRESS"}, "IN_PROGRESS"),
            "COMPLETED": ({"IN_PROGRESS"}, "WAITING_ACCEPTANCE"),
            "CANCELLED": ({"DRAFT", "APPROVED", "IN_PROGRESS", "REWORK"}, "CANCELLED"),
        }
        if event_type not in transitions:
            raise AppError("外包执行事件无效", code="VALIDATION_ERROR", status_code=400)
        allowed, target = transitions[event_type]
        if row.status not in allowed:
            raise AppError(
                "外包服务单状态不允许该事件", code="OUTSOURCING_STATE_INVALID", status_code=409
            )
        evidence = data.get("evidence") or None
        if event_type == "COMPLETED" and not evidence:
            raise AppError(
                "完成服务必须提交交付证据", code="OUTSOURCING_EVIDENCE_REQUIRED", status_code=400
            )
        self.repo.create_outsourcing_event(
            park_id=row.park_id,
            order_id=row.id,
            event_type=event_type,
            note=clean_text(data.get("note"), field="note", maximum=2000, required=False) or None,
            evidence_json=evidence,
            idempotency_key=key,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        row.status, row.lock_version = target, int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action=event_type.lower(),
            resource_type="OUTSOURCING_ORDER",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"status": target, "evidence_count": len(evidence or [])},
        )
        self._commit("OUTSOURCING_EVENT_CONFLICT", "外包执行事件并发冲突")
        return self._outsourcing_dict(row)

    def accept_outsourcing(
        self, order_id: int, data: dict[str, Any], *, key: str
    ) -> dict[str, Any]:
        self._permission("outsourcing:accept")
        previous = self.repo.event_by_key(key)
        if previous is not None:
            row = self.repo.outsourcing(order_id)
            if row is None or int(previous.order_id) != int(order_id):
                raise AppError("幂等键已用于其他验收", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._outsourcing_dict(row)
        row = self.repo.outsourcing(order_id, for_update=True)
        if row is None:
            raise AppError("外包服务单不存在", code="OUTSOURCING_ORDER_NOT_FOUND", status_code=404)
        if row.status != "WAITING_ACCEPTANCE":
            raise AppError(
                "外包服务尚未进入待验收", code="OUTSOURCING_STATE_INVALID", status_code=409
            )
        accepted = bool(data["accepted"])
        if not accepted and not clean_text(
            data.get("reason"), field="reason", maximum=1000, required=False
        ):
            raise AppError("拒绝验收必须填写返工原因", code="VALIDATION_ERROR", status_code=400)
        event_type, target = ("ACCEPTED", "ACCEPTED") if accepted else ("REWORK", "REWORK")
        self.repo.create_outsourcing_event(
            park_id=row.park_id,
            order_id=row.id,
            event_type=event_type,
            note=clean_text(data.get("reason"), field="reason", maximum=1000, required=False)
            or None,
            evidence_json=None,
            idempotency_key=key,
            actor_user_id=self.ctx.user_id or None,
            occurred_at=utc_now(),
        )
        row.status, row.lock_version = target, int(row.lock_version) + 1
        self.repo.save(row)
        if accepted and data.get("score") is not None:
            self.repo.create_evaluation(
                park_id=row.park_id,
                supplier_id=row.supplier_id,
                source_type="OUTSOURCING",
                source_id=row.id,
                score=int(data["score"]),
                comment=clean_text(
                    data.get("comment"), field="comment", maximum=1000, required=False
                )
                or None,
                evaluated_by=self.ctx.user_id or None,
                evaluated_at=utc_now(),
            )
        self.audit.record(
            action="accept" if accepted else "rework",
            resource_type="OUTSOURCING_ORDER",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "accepted": accepted,
                "score": data.get("score"),
                "settlement_state": row.settlement_state,
            },
        )
        self._commit("OUTSOURCING_ACCEPTANCE_CONFLICT", "外包验收并发冲突")
        return self._outsourcing_dict(row)
