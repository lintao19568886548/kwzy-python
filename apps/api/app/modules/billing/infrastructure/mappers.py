"""功能说明：Bill ORM 映射。"""

from __future__ import annotations

from decimal import Decimal

from app.infrastructure.database.models.billing import Bill, BillLine
from app.modules.billing.domain.entities import BillEntity, BillLineEntity


class BillMapper:
    @staticmethod
    def to_entity(m: Bill) -> BillEntity:
        return BillEntity(
            id=m.id,
            tenant_id=m.tenant_id,
            park_id=m.park_id,
            party_id=m.party_id,
            contract_id=m.contract_id,
            bill_no=m.bill_no,
            title=m.title,
            project_name=m.project_name,
            period_start=m.period_start,
            period_end=m.period_end,
            due_date=m.due_date,
            overdue_since=m.overdue_since,
            status=m.status,
            total_amount=Decimal(str(m.total_amount or 0)),
            paid_amount=Decimal(str(m.paid_amount or 0)),
            currency=m.currency,
            source=m.source,
            source_ref=m.source_ref,
            remark=m.remark,
            issued_at=m.issued_at,
            created_by=m.created_by,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def new_model(e: BillEntity) -> Bill:
        return Bill(
            tenant_id=e.tenant_id,
            park_id=e.park_id,
            party_id=e.party_id,
            contract_id=e.contract_id,
            bill_no=e.bill_no,
            title=e.title,
            project_name=e.project_name,
            period_start=e.period_start,
            period_end=e.period_end,
            due_date=e.due_date,
            overdue_since=e.overdue_since,
            status=e.status,
            total_amount=e.total_amount,
            paid_amount=e.paid_amount,
            currency=e.currency,
            source=e.source,
            source_ref=e.source_ref,
            remark=e.remark,
            issued_at=e.issued_at,
            created_by=e.created_by,
        )


class BillLineMapper:
    @staticmethod
    def new_model(e: BillLineEntity) -> BillLine:
        return BillLine(
            tenant_id=e.tenant_id,
            bill_id=e.bill_id,
            fee_code=e.fee_code,
            description=e.description,
            quantity=e.quantity,
            unit_price=e.unit_price,
            amount=e.amount,
            meter_reading_from=e.meter_reading_from,
            meter_reading_to=e.meter_reading_to,
            multiplier=e.multiplier,
            sort_order=e.sort_order,
        )
