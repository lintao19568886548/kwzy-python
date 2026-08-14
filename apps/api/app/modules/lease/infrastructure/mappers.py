"""Lease ORM to pure-domain mappings for current and immutable projections."""

from __future__ import annotations

from decimal import Decimal

from app.infrastructure.database.base import utc_now
from app.infrastructure.database.models.lease import (
    LeaseChangeOrder,
    LeaseChargeItem,
    LeaseContract,
    LeaseContractDocument,
    LeaseContractUnit,
    LeaseContractVersion,
    LeaseExitItem,
    LeaseExitSettlement,
    LeasePerformanceSchedule,
    LeaseTerm,
)
from app.modules.lease.domain.entities import (
    LeaseChangeOrderEntity,
    LeaseChargeItemEntity,
    LeaseContractDocumentEntity,
    LeaseContractEntity,
    LeaseContractUnitEntity,
    LeaseContractVersionEntity,
    LeaseExitItemEntity,
    LeaseExitSettlementEntity,
    LeasePerformanceScheduleEntity,
    LeaseTermEntity,
)
from app.modules.lease.domain.versioning import snapshot_checksum


class LeaseContractMapper:
    @staticmethod
    def to_entity(model: LeaseContract) -> LeaseContractEntity:
        return LeaseContractEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            park_id=model.park_id,
            party_id=model.party_id,
            contract_no=model.contract_no,
            contract_type=model.contract_type,
            currency=model.currency,
            status=model.status,
            approval_status=model.approval_status,
            start_date=model.start_date,
            end_date=model.end_date,
            signed_at=model.signed_at,
            effective_at=model.effective_at,
            terminated_at=model.terminated_at,
            increase_date=model.increase_date,
            increase_rate=model.increase_rate,
            deposit_amount=Decimal(str(model.deposit_amount or 0)),
            current_version_no=int(model.current_version_no or 0),
            lock_version=int(model.lock_version or 1),
            source_system=model.source_system,
            source_ref=model.source_ref,
            remark=model.remark,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def new_model(entity: LeaseContractEntity) -> LeaseContract:
        return LeaseContract(
            tenant_id=entity.tenant_id,
            park_id=entity.park_id,
            party_id=entity.party_id,
            contract_no=entity.contract_no,
            contract_type=entity.contract_type,
            currency=entity.currency,
            status=entity.status,
            approval_status=entity.approval_status,
            start_date=entity.start_date,
            end_date=entity.end_date,
            signed_at=entity.signed_at,
            effective_at=entity.effective_at,
            terminated_at=entity.terminated_at,
            increase_date=entity.increase_date,
            increase_rate=entity.increase_rate,
            deposit_amount=entity.deposit_amount,
            current_version_no=entity.current_version_no,
            lock_version=entity.lock_version,
            source_system=entity.source_system or "MANUAL",
            source_ref=entity.source_ref,
            remark=entity.remark,
            created_by=entity.created_by,
        )

    @staticmethod
    def apply_entity(model: LeaseContract, entity: LeaseContractEntity) -> LeaseContract:
        model.park_id = entity.park_id
        model.party_id = entity.party_id
        model.contract_no = entity.contract_no
        model.contract_type = entity.contract_type
        model.currency = entity.currency
        model.status = entity.status
        model.approval_status = entity.approval_status
        model.start_date = entity.start_date
        model.end_date = entity.end_date
        model.signed_at = entity.signed_at
        model.effective_at = entity.effective_at
        model.terminated_at = entity.terminated_at
        model.increase_date = entity.increase_date
        model.increase_rate = entity.increase_rate
        model.deposit_amount = entity.deposit_amount
        model.current_version_no = entity.current_version_no
        model.lock_version = entity.lock_version
        model.source_system = entity.source_system or "MANUAL"
        model.source_ref = entity.source_ref
        model.remark = entity.remark
        return model


class LeaseContractUnitMapper:
    @staticmethod
    def to_entity(model: LeaseContractUnit) -> LeaseContractUnitEntity:
        return LeaseContractUnitEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            contract_id=model.contract_id,
            unit_id=model.unit_id,
            occupied_area=Decimal(str(model.occupied_area or 0)),
            unit_rent_price=Decimal(str(model.unit_rent_price or 0)),
        )

    @staticmethod
    def new_model(entity: LeaseContractUnitEntity) -> LeaseContractUnit:
        return LeaseContractUnit(
            tenant_id=entity.tenant_id,
            contract_id=entity.contract_id,
            unit_id=entity.unit_id,
            occupied_area=entity.occupied_area,
            unit_rent_price=entity.unit_rent_price,
        )


class LeaseTermMapper:
    @staticmethod
    def to_entity(model: LeaseTerm) -> LeaseTermEntity:
        return LeaseTermEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            contract_id=model.contract_id,
            term_type=model.term_type,
            effective_date=model.effective_date,
            end_date=model.end_date,
            rate=model.rate,
            amount=model.amount,
            description=model.description,
            sort_order=int(model.sort_order or 0),
            created_at=model.created_at,
        )

    @staticmethod
    def new_model(entity: LeaseTermEntity) -> LeaseTerm:
        return LeaseTerm(
            tenant_id=entity.tenant_id,
            contract_id=entity.contract_id,
            term_type=entity.term_type,
            effective_date=entity.effective_date,
            end_date=entity.end_date,
            rate=entity.rate,
            amount=entity.amount,
            description=entity.description,
            sort_order=entity.sort_order,
            created_at=entity.created_at or utc_now(),
        )


class LeaseContractVersionMapper:
    @staticmethod
    def to_entity(model: LeaseContractVersion) -> LeaseContractVersionEntity:
        return LeaseContractVersionEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            contract_id=model.contract_id,
            version_no=model.version_no,
            schema_version=model.schema_version,
            snapshot=dict(model.snapshot_json),
            checksum=model.checksum,
            effective_at=model.effective_at,
            reason=model.reason,
            created_by=model.created_by,
            change_order_id=model.change_order_id,
            exit_settlement_id=model.exit_settlement_id,
            created_at=model.created_at,
        )

    @staticmethod
    def new_model(entity: LeaseContractVersionEntity, *, park_id: int) -> LeaseContractVersion:
        return LeaseContractVersion(
            tenant_id=entity.tenant_id,
            park_id=park_id,
            contract_id=entity.contract_id,
            version_no=entity.version_no,
            status=str(entity.snapshot.get("contract", {}).get("status") or "ACTIVE"),
            schema_version=entity.schema_version,
            snapshot_json=entity.snapshot,
            checksum=entity.checksum,
            reason=entity.reason,
            change_order_id=entity.change_order_id,
            exit_settlement_id=entity.exit_settlement_id,
            effective_at=entity.effective_at,
            created_by=entity.created_by,
        )


class LeaseChargeItemMapper:
    @staticmethod
    def to_entity(model: LeaseChargeItem) -> LeaseChargeItemEntity:
        return LeaseChargeItemEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            contract_id=model.contract_id,
            charge_code=model.charge_code,
            charge_type=model.charge_type,
            calculation_method=model.calculation_method,
            billing_cycle=model.billing_cycle,
            currency=model.currency,
            start_date=model.start_date,
            end_date=model.end_date,
            due_day=model.due_day,
            amount=model.amount,
            unit_price=model.unit_price,
            tax_rate=Decimal(str(model.tax_rate or 0)),
            sort_order=model.sort_order,
            rule_config={"rules": model.rules_json or [], "review_status": model.review_status},
        )

    @staticmethod
    def new_model(entity: LeaseChargeItemEntity) -> LeaseChargeItem:
        return LeaseChargeItem(
            tenant_id=entity.tenant_id,
            contract_id=entity.contract_id,
            charge_code=entity.charge_code,
            charge_type=entity.charge_type,
            calculation_method=entity.calculation_method,
            billing_cycle=entity.billing_cycle,
            currency=entity.currency,
            start_date=entity.start_date,
            end_date=entity.end_date,
            due_day=entity.due_day,
            amount=entity.amount,
            unit_price=entity.unit_price,
            tax_rate=entity.tax_rate,
            rules_json=list(entity.rule_config.get("rules") or []),
            review_status=str(entity.rule_config.get("review_status") or "CONFIRMED"),
            sort_order=entity.sort_order,
        )


class LeasePerformanceScheduleMapper:
    @staticmethod
    def to_entity(model: LeasePerformanceSchedule) -> LeasePerformanceScheduleEntity:
        return LeasePerformanceScheduleEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            contract_id=model.contract_id,
            contract_version_no=model.contract_version_no,
            charge_item_id=model.charge_item_id,
            charge_code=model.charge_code,
            schedule_key=model.deterministic_key,
            period_start=model.period_start,
            period_end=model.period_end,
            due_date=model.due_date,
            currency=model.currency,
            area=Decimal(str(model.area or 0)),
            unit_price=model.unit_price,
            net_amount=Decimal(str(model.net_amount or 0)),
            tax_amount=Decimal(str(model.tax_amount or 0)),
            gross_amount=Decimal(str(model.gross_amount or 0)),
            status=model.status,
            rule_refs=tuple(model.rule_refs_json or []),
        )

    @staticmethod
    def new_model(entity: LeasePerformanceScheduleEntity) -> LeasePerformanceSchedule:
        return LeasePerformanceSchedule(
            tenant_id=entity.tenant_id,
            contract_id=entity.contract_id,
            contract_version_no=entity.contract_version_no,
            charge_item_id=entity.charge_item_id,
            charge_code=entity.charge_code,
            deterministic_key=entity.schedule_key,
            period_start=entity.period_start,
            period_end=entity.period_end,
            due_date=entity.due_date,
            currency=entity.currency,
            area=entity.area,
            unit_price=entity.unit_price,
            net_amount=entity.net_amount,
            tax_amount=entity.tax_amount,
            gross_amount=entity.gross_amount,
            status=entity.status,
            rule_refs_json=list(entity.rule_refs),
        )


class LeaseChangeOrderMapper:
    @staticmethod
    def to_entity(model: LeaseChangeOrder) -> LeaseChangeOrderEntity:
        return LeaseChangeOrderEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            contract_id=model.contract_id,
            change_no=model.change_no,
            change_type=model.change_type,
            reason=model.reason,
            effective_date=model.effective_date,
            base_version_no=model.base_version_no,
            proposed_snapshot=dict(model.proposal_json),
            status=model.status,
            schema_version=model.proposal_schema_version,
            lock_version=model.lock_version,
            approval_request_id=model.approval_id,
            applied_version_no=model.applied_version_no,
            idempotency_key=model.idempotency_key,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def new_model(entity: LeaseChangeOrderEntity, *, park_id: int) -> LeaseChangeOrder:
        return LeaseChangeOrder(
            tenant_id=entity.tenant_id,
            park_id=park_id,
            contract_id=entity.contract_id,
            change_no=entity.change_no,
            change_type=entity.change_type,
            status=entity.status,
            base_version_no=entity.base_version_no,
            applied_version_no=entity.applied_version_no,
            effective_date=entity.effective_date,
            reason=entity.reason,
            proposal_json=entity.proposed_snapshot,
            proposal_checksum=snapshot_checksum(entity.proposed_snapshot),
            proposal_schema_version=entity.schema_version,
            approval_id=entity.approval_request_id,
            idempotency_key=entity.idempotency_key,
            lock_version=entity.lock_version,
            created_by=entity.created_by,
        )


class LeaseContractDocumentMapper:
    @staticmethod
    def to_entity(model: LeaseContractDocument) -> LeaseContractDocumentEntity:
        return LeaseContractDocumentEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            contract_id=model.contract_id,
            attachment_id=model.attachment_id,
            document_type=model.document_type,
            document_version=model.document_version,
            status=model.status,
            checksum=model.checksum,
            is_main=model.is_main,
            contract_version_no=model.contract_version_no,
            change_order_id=model.change_order_id,
            exit_settlement_id=model.exit_settlement_id,
            signature_provider=model.signature_provider,
            signature_ref=model.signature_ref,
            signed_at=model.signed_at,
            live_verified=model.live_verified,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    @staticmethod
    def new_model(entity: LeaseContractDocumentEntity, *, park_id: int) -> LeaseContractDocument:
        return LeaseContractDocument(
            tenant_id=entity.tenant_id,
            park_id=park_id,
            contract_id=entity.contract_id,
            contract_version_no=entity.contract_version_no,
            change_order_id=entity.change_order_id,
            exit_settlement_id=entity.exit_settlement_id,
            attachment_id=entity.attachment_id,
            document_type=entity.document_type,
            document_version=entity.document_version,
            checksum=entity.checksum,
            status=entity.status,
            is_main=entity.is_main,
            signature_provider=entity.signature_provider,
            signature_ref=entity.signature_ref,
            live_verified=entity.live_verified,
            signed_at=entity.signed_at,
            created_by=entity.created_by,
        )


class LeaseExitItemMapper:
    @staticmethod
    def to_entity(model: LeaseExitItem) -> LeaseExitItemEntity:
        return LeaseExitItemEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            settlement_id=model.settlement_id,
            item_type=model.item_type,
            amount=Decimal(str(model.amount or 0)),
            description=model.description,
            evidence_attachment_id=model.evidence_attachment_id,
            approved=model.approved,
            source_type=model.source_type,
            source_ref=model.source_ref,
            sort_order=model.sort_order,
        )

    @staticmethod
    def new_model(entity: LeaseExitItemEntity) -> LeaseExitItem:
        if entity.settlement_id is None or entity.tenant_id is None:
            raise ValueError("settlement_id and tenant_id are required")
        return LeaseExitItem(
            tenant_id=entity.tenant_id,
            settlement_id=entity.settlement_id,
            item_type=entity.item_type,
            description=entity.description,
            amount=entity.amount,
            approved=entity.approved,
            evidence_attachment_id=entity.evidence_attachment_id,
            source_type=entity.source_type,
            source_ref=entity.source_ref,
            sort_order=entity.sort_order,
        )


class LeaseExitSettlementMapper:
    @staticmethod
    def to_entity(
        model: LeaseExitSettlement,
        *,
        items: list[LeaseExitItemEntity] | None = None,
    ) -> LeaseExitSettlementEntity:
        return LeaseExitSettlementEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            contract_id=model.contract_id,
            change_order_id=model.change_order_id,
            settlement_no=model.settlement_no,
            contract_version_no=model.contract_version_no,
            planned_handover_date=model.handover_date,
            held_deposit_amount=Decimal(str(model.held_deposit_amount or 0)),
            outstanding_amount=Decimal(str(model.outstanding_amount or 0)),
            outstanding_source=model.outstanding_source,
            outstanding_as_of=model.outstanding_as_of,
            status=model.status,
            lock_version=model.lock_version,
            inspection_summary=model.inspection_summary,
            meter_readings=list(model.meter_readings_json or []),
            items=items or [],
            receivable_total=Decimal(str(model.receivable_total or 0)),
            deduction_total=Decimal(str(model.deduction_total or 0)),
            refund_adjustment_total=Decimal(str(model.refund_adjustment_total or 0)),
            net_due_from_party=Decimal(str(model.net_due_from_party or 0)),
            net_due_to_party=Decimal(str(model.net_due_to_party or 0)),
            calculation_checksum=model.checksum,
            financial_clearance_status=model.financial_clearance_status,
            financial_clearance_ref=model.clearance_reference,
            financial_clearance_reason=model.clearance_reason,
            approval_request_id=model.approval_id,
            idempotency_key=model.idempotency_key,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def new_model(entity: LeaseExitSettlementEntity, *, park_id: int) -> LeaseExitSettlement:
        return LeaseExitSettlement(
            tenant_id=entity.tenant_id,
            park_id=park_id,
            contract_id=entity.contract_id,
            change_order_id=entity.change_order_id,
            settlement_no=entity.settlement_no,
            contract_version_no=entity.contract_version_no,
            status=entity.status,
            handover_date=entity.planned_handover_date,
            inspection_summary=entity.inspection_summary,
            meter_readings_json=entity.meter_readings,
            held_deposit_amount=entity.held_deposit_amount,
            outstanding_amount=entity.outstanding_amount,
            outstanding_source=entity.outstanding_source,
            outstanding_as_of=entity.outstanding_as_of or utc_now(),
            receivable_total=entity.receivable_total,
            deduction_total=entity.deduction_total,
            refund_adjustment_total=entity.refund_adjustment_total,
            net_due_from_party=entity.net_due_from_party,
            net_due_to_party=entity.net_due_to_party,
            financial_clearance_status=entity.financial_clearance_status,
            clearance_reference=entity.financial_clearance_ref,
            clearance_reason=entity.financial_clearance_reason,
            approval_id=entity.approval_request_id,
            checksum=entity.calculation_checksum or "",
            idempotency_key=entity.idempotency_key,
            lock_version=entity.lock_version,
            created_by=entity.created_by,
        )
