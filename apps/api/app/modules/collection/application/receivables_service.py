"""Receipt matching, dunning and approval-gated receivable treatment orchestration."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.infrastructure.platform.idempotency import (
    begin_idempotent,
    complete_idempotent,
    normalize_idempotency_key,
    request_hash,
)
from app.infrastructure.platform.number_sequence import next_number
from app.modules.billing.domain.rules import (
    aging_level,
    collectible_open_amount,
    effective_due_date,
    money,
)
from app.modules.billing.infrastructure.bill_repository import BillRepository
from app.modules.collection.application.payment_service import PaymentService
from app.modules.collection.domain.rules import mask_account
from app.modules.collection.infrastructure.receivables_repository import ReceivablesRepository
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.workbench.application.work_item_service import WorkItemService
from app.modules.workflow.infrastructure.approval_repository import ApprovalRepository
from app.shared.tenant_context import TenantContext

LOCAL_RECEIPT_CHANNELS = frozenset({"BANK_IMPORT", "OFFLINE_TRANSFER", "CASH", "POS"})
ALL_RECEIPT_CHANNELS = (
    "BANK_IMPORT",
    "BANK_API",
    "OFFLINE_TRANSFER",
    "PAYMENT_LINK",
    "WECHAT",
    "ALIPAY",
    "AGGREGATE",
    "CASH",
    "POS",
)
ADJUSTMENT_TYPES = frozenset({"WAIVER", "EXTENSION", "BAD_DEBT", "DISPUTE", "DISPUTE_RESOLUTION"})


class ReceivablesService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = ReceivablesRepository(session, ctx)
        self.bills = BillRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.payments = PaymentService(session, ctx)
        self.approvals = ApprovalRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.work_items = WorkItemService(session, ctx)

    @staticmethod
    def _datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except (TypeError, ValueError) as exc:
            raise AppError("received_at 无效", code="VALIDATION_ERROR", status_code=400) from exc

    @staticmethod
    def _date(value: Any) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError) as exc:
            raise AppError("日期无效", code="VALIDATION_ERROR", status_code=400) from exc

    @staticmethod
    def _normalized_text(value: str | None) -> str:
        return "".join((value or "").split()).casefold()

    def capabilities(self) -> dict[str, Any]:
        channels = []
        for code in ALL_RECEIPT_CHANNELS:
            channels.append(
                {
                    "channel": code,
                    "status": "AVAILABLE" if code in LOCAL_RECEIPT_CHANNELS else "NOT_CONNECTED",
                    "mode": "LOCAL_IMPORT"
                    if code == "BANK_IMPORT"
                    else "MANUAL"
                    if code in LOCAL_RECEIPT_CHANNELS
                    else "EXTERNAL_ADAPTER",
                }
            )
        return {"channels": channels, "automatic_financial_posting": False}

    def _receipt_dict(self, row: Any, *, with_candidates: bool = False) -> dict:
        data = {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "party_id": int(row.party_id) if row.party_id is not None else None,
            "transaction_no": row.transaction_no,
            "amount": str(money(row.amount)),
            "currency": row.currency,
            "received_at": row.received_at.isoformat(),
            "channel": row.channel,
            "source_provider": row.source_provider,
            "source_ref": row.source_ref,
            "payer_name": row.payer_name,
            "payer_account_masked": row.payer_account_masked,
            "bank_reference": row.bank_reference,
            "purpose": row.purpose,
            "status": row.status,
            "exception_code": row.exception_code,
            "review_remark": row.review_remark,
            "dispute_reason": row.dispute_reason,
            "dispute_resolution": row.dispute_resolution,
            "payment_id": int(row.payment_id) if row.payment_id is not None else None,
            "lock_version": int(row.lock_version),
        }
        if with_candidates:
            data["candidates"] = [
                {
                    "id": int(item.id),
                    "bill_id": int(item.bill_id),
                    "score": int(item.score),
                    "rank": int(item.rank),
                    "proposed_amount": str(money(item.proposed_amount)),
                    "rule_codes": list(item.rule_codes_json or []),
                }
                for item in self.repo.candidates(int(row.id))
            ]
        return data

    def ingest_receipt(self, data: dict[str, Any], *, commit: bool = True) -> dict:
        if not self.ctx.has_permission("payment:import"):
            raise AppError("无到账导入权限", code="PERMISSION_DENIED", status_code=403)
        park_id = int(data["park_id"])
        if not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        channel = str(data.get("channel") or "").strip().upper()
        if channel not in ALL_RECEIPT_CHANNELS:
            raise AppError("到账渠道无效", code="VALIDATION_ERROR", status_code=400)
        if channel not in LOCAL_RECEIPT_CHANNELS:
            raise AppError("到账渠道未连接", code="RECEIPT_PROVIDER_NOT_CONNECTED", status_code=409)
        provider = str(data.get("source_provider") or "MANUAL").strip().upper()
        source_ref = str(data.get("source_ref") or "").strip()
        if not source_ref:
            raise AppError("source_ref 必填", code="VALIDATION_ERROR", status_code=400)
        amount = money(data.get("amount") or 0)
        if amount <= 0:
            raise AppError("到账金额须大于 0", code="VALIDATION_ERROR", status_code=400)
        party_id = int(data["party_id"]) if data.get("party_id") is not None else None
        if party_id is not None:
            party = self.payments.parties.get_by_id(party_id)
            if party is None:
                raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        previous = self.repo.receipt_by_source(provider, source_ref)
        if previous is not None:
            if (
                int(previous.park_id) == park_id
                and (
                    (int(previous.party_id) if previous.party_id is not None else None) == party_id
                )
                and money(previous.amount) == amount
                and previous.channel == channel
                and previous.currency == str(data.get("currency") or "CNY").strip().upper()
                and previous.received_at == self._datetime(data.get("received_at"))
                and previous.payer_account_masked == mask_account(data.get("payer_account"))
            ):
                return self._receipt_dict(previous, with_candidates=True)
            raise AppError("来源流水内容冲突", code="RECEIPT_SOURCE_CONFLICT", status_code=409)
        received_at = self._datetime(data.get("received_at"))
        sequence = next_number(
            self.session,
            tenant_id=self.ctx.tenant_id,
            biz_type="RECEIPT",
            period_key=received_at.strftime("%Y%m%d"),
        )
        try:
            row = self.repo.create_receipt(
                park_id=park_id,
                party_id=party_id,
                transaction_no=f"R{received_at:%Y%m%d}{sequence:05d}",
                amount=amount,
                currency=str(data.get("currency") or "CNY").strip().upper(),
                received_at=received_at,
                channel=channel,
                source_provider=provider,
                source_ref=source_ref,
                payer_name=str(data.get("payer_name") or "").strip() or None,
                payer_account_masked=mask_account(data.get("payer_account")),
                bank_reference=str(data.get("bank_reference") or "").strip() or None,
                purpose=str(data.get("purpose") or "").strip() or None,
                status="PENDING",
                lock_version=1,
                created_by=self.ctx.user_id,
            )
            self.audit.record(
                action="ingest",
                resource_type="RECEIPT_TRANSACTION",
                resource_id=row.id,
                park_id=park_id,
                detail={"channel": channel, "source_provider": provider, "amount": str(amount)},
            )
            if commit:
                self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "到账流水并发冲突", code="RECEIPT_SOURCE_CONFLICT", status_code=409
            ) from exc
        return self._receipt_dict(row)

    def import_receipts(self, rows: list[dict[str, Any]]) -> dict:
        if len(rows) > 500:
            raise AppError("单批最多 500 条", code="VALIDATION_ERROR", status_code=400)
        try:
            results = [self.ingest_receipt(row, commit=False) for row in rows]
            self.session.commit()
            return {"count": len(results), "items": results}
        except AppError:
            self.session.rollback()
            raise

    def list_receipts(
        self, *, page: int, page_size: int, status: str | None, park_id: int | None
    ) -> dict:
        if not self.ctx.has_permission("payment:read"):
            raise AppError("无到账查看权限", code="PERMISSION_DENIED", status_code=403)
        page = max(int(page), 1)
        size = min(max(int(page_size), 1), 200)
        rows, total = self.repo.list_receipts(
            offset=(page - 1) * size, limit=size, status=status, park_id=park_id
        )
        return {
            "total": total,
            "page": page,
            "page_size": size,
            "items": [self._receipt_dict(row) for row in rows],
        }

    def receipt_detail(self, receipt_id: int) -> dict:
        if not self.ctx.has_permission("payment:read"):
            raise AppError("无到账查看权限", code="PERMISSION_DENIED", status_code=403)
        row = self.repo.receipt(receipt_id)
        if row is None:
            raise AppError("到账流水不存在", code="RECEIPT_NOT_FOUND", status_code=404)
        return self._receipt_dict(row, with_candidates=True)

    def run_match(self, receipt_id: int, *, expected_version: int) -> dict:
        if not self.ctx.has_permission("payment:review"):
            raise AppError("无到账匹配权限", code="PERMISSION_DENIED", status_code=403)
        receipt = self.repo.receipt(receipt_id, for_update=True)
        if receipt is None:
            raise AppError("到账流水不存在", code="RECEIPT_NOT_FOUND", status_code=404)
        if int(receipt.lock_version) != int(expected_version):
            raise AppError("到账版本冲突", code="RECEIPT_VERSION_CONFLICT", status_code=409)
        if receipt.status in {"CONFIRMED", "DISPUTED", "REJECTED"}:
            raise AppError("到账状态不可匹配", code="RECEIPT_STATUS_INVALID", status_code=409)
        candidates: list[dict[str, Any]] = []
        for bill, party_name in self.repo.candidate_bills(
            park_id=int(receipt.park_id),
            party_id=int(receipt.party_id) if receipt.party_id is not None else None,
            reference=receipt.bank_reference or receipt.purpose,
        ):
            try:
                open_value = collectible_open_amount(
                    bill.total_amount,
                    bill.paid_amount,
                    bill.waiver_amount,
                    bill.bad_debt_amount,
                )
            except ValueError:
                continue
            if open_value <= 0:
                continue
            rules: list[str] = []
            score = 0
            reference = self._normalized_text(receipt.bank_reference or receipt.purpose)
            if reference and self._normalized_text(bill.bill_no) in reference:
                rules.append("EXACT_BILL_REFERENCE")
                score += 70
            if receipt.party_id is not None and int(receipt.party_id) == int(bill.party_id):
                rules.append("SAME_PARTY")
                score += 20
            if receipt.payer_name and self._normalized_text(
                receipt.payer_name
            ) == self._normalized_text(party_name):
                rules.append("EXACT_PAYER_NAME")
                score += 20
            if money(receipt.amount) == open_value:
                rules.append("EXACT_OPEN_AMOUNT")
                score += 20
            if score <= 0:
                continue
            candidates.append(
                {
                    "bill": bill,
                    "score": min(score, 100),
                    "rules": rules,
                    "open": open_value,
                }
            )
        candidates.sort(
            key=lambda item: (
                -item["score"],
                item["bill"].due_date or date.max,
                int(item["bill"].id),
            )
        )
        remaining = money(receipt.amount)
        candidate_rows: list[dict[str, Any]] = []
        inferred_party: int | None = int(receipt.party_id) if receipt.party_id is not None else None
        for rank, item in enumerate(candidates, start=1):
            if remaining <= 0:
                break
            bill = item["bill"]
            if inferred_party is None:
                inferred_party = int(bill.party_id)
            if int(bill.party_id) != inferred_party:
                continue
            proposed = min(item["open"], remaining)
            candidate_rows.append(
                {
                    "bill_id": int(bill.id),
                    "score": item["score"],
                    "rank": rank,
                    "proposed_amount": proposed,
                    "rule_codes_json": item["rules"],
                    "created_at": utc_now(),
                }
            )
            remaining = money(remaining - proposed)
        self.repo.replace_candidates(int(receipt.id), candidate_rows)
        receipt.party_id = inferred_party
        receipt.status = "SUGGESTED" if candidate_rows else "EXCEPTION"
        receipt.exception_code = None if candidate_rows else "NO_MATCH_CANDIDATE"
        receipt.lock_version += 1
        self.audit.record(
            action="match",
            resource_type="RECEIPT_TRANSACTION",
            resource_id=receipt.id,
            park_id=receipt.park_id,
            detail={"candidate_count": len(candidate_rows)},
        )
        self.session.commit()
        return self._receipt_dict(receipt, with_candidates=True)

    def confirm_receipt(
        self,
        receipt_id: int,
        *,
        expected_version: int,
        party_id: int | None,
        allocations: list[dict[str, Any]] | None,
        remark: str | None,
    ) -> dict:
        if not self.ctx.has_permission("payment:review"):
            raise AppError("无到账复核权限", code="PERMISSION_DENIED", status_code=403)
        receipt = self.repo.receipt(receipt_id, for_update=True)
        if receipt is None:
            raise AppError("到账流水不存在", code="RECEIPT_NOT_FOUND", status_code=404)
        if int(receipt.lock_version) != int(expected_version):
            raise AppError("到账版本冲突", code="RECEIPT_VERSION_CONFLICT", status_code=409)
        if receipt.status not in {"PENDING", "SUGGESTED", "EXCEPTION"}:
            raise AppError("到账状态不可确认", code="RECEIPT_STATUS_INVALID", status_code=409)
        selected = allocations
        if selected is None:
            selected = [
                {"bill_id": int(row.bill_id), "amount": str(row.proposed_amount)}
                for row in self.repo.candidates(receipt_id)
            ]
        resolved_party = party_id or receipt.party_id
        if resolved_party is None:
            raise AppError("确认前须选择主体", code="RECEIPT_PARTY_REQUIRED", status_code=400)
        channel_method = {
            "CASH": "CASH",
            "POS": "POS",
            "WECHAT": "WECHAT",
            "ALIPAY": "ALIPAY",
            "AGGREGATE": "AGGREGATE",
        }.get(receipt.channel, "TRANSFER")
        payment = self.payments.create_payment(
            {
                "park_id": int(receipt.park_id),
                "party_id": int(resolved_party),
                "amount": str(receipt.amount),
                "method": channel_method,
                "paid_at": receipt.received_at,
                "payment_no": f"RP-{receipt.transaction_no}",
                "remark": remark or f"到账复核 {receipt.transaction_no}",
                "allocations": selected,
            },
            source_receipt_id=int(receipt.id),
            permission_code="payment:review",
            commit=False,
        )
        receipt.party_id = int(resolved_party)
        receipt.status = "CONFIRMED"
        receipt.payment_id = int(payment["id"])
        receipt.reviewed_by = self.ctx.user_id
        receipt.reviewed_at = utc_now()
        receipt.review_remark = remark
        receipt.exception_code = None
        receipt.lock_version += 1
        self.audit.record(
            action="confirm",
            resource_type="RECEIPT_TRANSACTION",
            resource_id=receipt.id,
            park_id=receipt.park_id,
            detail={"payment_id": payment["id"], "allocation_count": len(selected)},
        )
        self.session.commit()
        return {"receipt": self._receipt_dict(receipt, with_candidates=True), "payment": payment}

    def mark_exception(
        self, receipt_id: int, *, expected_version: int, code: str, remark: str
    ) -> dict:
        if not self.ctx.has_permission("payment:review"):
            raise AppError("无到账复核权限", code="PERMISSION_DENIED", status_code=403)
        receipt = self.repo.receipt(receipt_id, for_update=True)
        if receipt is None:
            raise AppError("到账流水不存在", code="RECEIPT_NOT_FOUND", status_code=404)
        if int(receipt.lock_version) != int(expected_version):
            raise AppError("到账版本冲突", code="RECEIPT_VERSION_CONFLICT", status_code=409)
        if receipt.status in {"CONFIRMED", "REJECTED", "DISPUTED"}:
            raise AppError("到账状态不可标记异常", code="RECEIPT_STATUS_INVALID", status_code=409)
        receipt.status = "EXCEPTION"
        receipt.exception_code = code.strip().upper()
        receipt.review_remark = remark.strip()
        receipt.reviewed_by = self.ctx.user_id
        receipt.reviewed_at = utc_now()
        receipt.lock_version += 1
        self.audit.record(
            action="exception",
            resource_type="RECEIPT_TRANSACTION",
            resource_id=receipt.id,
            park_id=receipt.park_id,
            detail={"exception_code": receipt.exception_code},
        )
        self.session.commit()
        return self._receipt_dict(receipt, with_candidates=True)

    def raise_dispute(self, receipt_id: int, *, expected_version: int, reason: str) -> dict:
        if not self.ctx.has_permission("payment:review"):
            raise AppError("无到账复核权限", code="PERMISSION_DENIED", status_code=403)
        receipt = self.repo.receipt(receipt_id, for_update=True)
        if receipt is None:
            raise AppError("到账流水不存在", code="RECEIPT_NOT_FOUND", status_code=404)
        if int(receipt.lock_version) != int(expected_version):
            raise AppError("到账版本冲突", code="RECEIPT_VERSION_CONFLICT", status_code=409)
        if receipt.status not in {"PENDING", "SUGGESTED", "EXCEPTION"}:
            raise AppError("到账状态不可发起争议", code="RECEIPT_STATUS_INVALID", status_code=409)
        receipt.status = "DISPUTED"
        receipt.dispute_reason = reason.strip()
        receipt.dispute_resolution = None
        receipt.lock_version += 1
        self.work_items.ensure_from_source(
            source_type="RECEIPT_DISPUTE",
            source_id=str(receipt.id),
            item_type="RECEIPT_DISPUTE_REVIEW",
            title=f"到账争议待复核 {receipt.transaction_no}",
            park_id=int(receipt.park_id),
            priority="URGENT",
            commit=False,
        )
        self.audit.record(
            action="raise_dispute",
            resource_type="RECEIPT_TRANSACTION",
            resource_id=receipt.id,
            park_id=receipt.park_id,
            detail={},
        )
        self.session.commit()
        return self._receipt_dict(receipt, with_candidates=True)

    def resolve_dispute(
        self, receipt_id: int, *, expected_version: int, decision: str, remark: str
    ) -> dict:
        if not self.ctx.has_permission("payment:dispute_review"):
            raise AppError("无到账争议复核权限", code="PERMISSION_DENIED", status_code=403)
        receipt = self.repo.receipt(receipt_id, for_update=True)
        if receipt is None:
            raise AppError("到账流水不存在", code="RECEIPT_NOT_FOUND", status_code=404)
        if int(receipt.lock_version) != int(expected_version):
            raise AppError("到账版本冲突", code="RECEIPT_VERSION_CONFLICT", status_code=409)
        if receipt.status != "DISPUTED":
            raise AppError("到账非争议状态", code="RECEIPT_STATUS_INVALID", status_code=409)
        normalized = decision.strip().upper()
        if normalized not in {"RETURN_TO_FINANCE", "REJECT_RECEIPT"}:
            raise AppError("争议结论无效", code="VALIDATION_ERROR", status_code=400)
        receipt.status = "PENDING" if normalized == "RETURN_TO_FINANCE" else "REJECTED"
        receipt.dispute_resolution = normalized
        receipt.dispute_reviewed_by = self.ctx.user_id
        receipt.dispute_reviewed_at = utc_now()
        receipt.review_remark = remark.strip()
        receipt.lock_version += 1
        self.work_items.complete_by_source(
            source_type="RECEIPT_DISPUTE",
            source_id=str(receipt.id),
            item_type="RECEIPT_DISPUTE_REVIEW",
            commit=False,
        )
        self.audit.record(
            action="resolve_dispute",
            resource_type="RECEIPT_TRANSACTION",
            resource_id=receipt.id,
            park_id=receipt.park_id,
            detail={"decision": normalized},
        )
        self.session.commit()
        return self._receipt_dict(receipt, with_candidates=True)

    @staticmethod
    def _aging_bill(bill, as_of: date) -> dict[str, Any] | None:
        try:
            open_value = collectible_open_amount(
                bill.total_amount,
                bill.paid_amount,
                bill.waiver_amount,
                bill.bad_debt_amount,
            )
        except ValueError:
            return None
        due = effective_due_date(bill.due_date, bill.deferred_due_date)
        if bill.collection_hold or due is None or open_value <= 0 or due >= as_of:
            return None
        days = (as_of - due).days
        level = aging_level(days)
        if level is None:
            return None
        return {
            "bill": bill,
            "bill_id": int(bill.id),
            "park_id": int(bill.park_id),
            "party_id": int(bill.party_id),
            "effective_due_date": due,
            "overdue_days": days,
            "level": level,
            "open_amount": open_value,
        }

    def _dunning_items(self, *, day: date, park_id: int | None) -> list[dict[str, Any]]:
        return [
            item
            for bill in self.repo.open_bills_for_dunning(park_id=park_id)
            if (item := self._aging_bill(bill, day)) is not None
        ]

    def dunning_preview(self, *, as_of: Any, park_id: int | None) -> dict:
        if not self.ctx.has_permission("collection:read"):
            raise AppError("无催缴查看权限", code="PERMISSION_DENIED", status_code=403)
        day = self._date(as_of)
        items = self._dunning_items(day=day, park_id=park_id)
        return {
            "mode": "PREVIEW",
            "as_of": day.isoformat(),
            "total": len(items),
            "amount": str(money(sum(item["open_amount"] for item in items))),
            "items": [
                {
                    "bill_id": item["bill_id"],
                    "park_id": item["park_id"],
                    "party_id": item["party_id"],
                    "effective_due_date": item["effective_due_date"].isoformat(),
                    "overdue_days": item["overdue_days"],
                    "level": item["level"],
                    "open_amount": str(money(item["open_amount"])),
                }
                for item in items
            ],
        }

    def dunning_apply(
        self, *, as_of: Any, park_id: int | None, idempotency_key: str | None
    ) -> dict:
        if not self.ctx.has_permission("collection:run"):
            raise AppError("无自动催缴权限", code="PERMISSION_DENIED", status_code=403)
        day = self._date(as_of)
        idem = normalize_idempotency_key(idempotency_key)
        if not idem:
            raise AppError("Idempotency-Key 必填", code="IDEMPOTENCY_KEY_REQUIRED", status_code=400)
        body_hash = request_hash({"as_of": day.isoformat(), "park_id": park_id})
        cached = begin_idempotent(
            self.session,
            tenant_id=self.ctx.tenant_id,
            user_id=self.ctx.user_id,
            operation="collection.dunning.apply",
            idem_key=idem,
            body_hash=body_hash,
        )
        if cached is not None:
            cached_park = cached.get("park_id")
            if cached_park is not None and not self.ctx.allows_park(int(cached_park)):
                raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
            return cached
        run_key = hashlib.sha256(f"{self.ctx.tenant_id}:{idem}".encode()).hexdigest()
        items = self._dunning_items(day=day, park_id=park_id)
        run = self.repo.create_dunning_run(
            park_id=park_id,
            as_of=day,
            mode="APPLY",
            run_key=run_key,
            status="RUNNING",
            created_by=self.ctx.user_id,
        )
        created = escalated = unchanged = 0
        try:
            for item in items:
                active = self.repo.active_cases_for_bill(item["bill_id"], for_update=True)
                if len(active) > 1:
                    raise AppError(
                        "历史活动催缴案件重复，需人工处置",
                        code="COLLECTION_CASE_LEGACY_CONFLICT",
                        status_code=409,
                    )
                if active:
                    case = active[0]
                    if case.level == item["level"]:
                        unchanged += 1
                    else:
                        case.level = item["level"]
                        escalated += 1
                else:
                    case = self.repo.create_case(
                        park_id=item["park_id"],
                        party_id=item["party_id"],
                        bill_id=item["bill_id"],
                        status="OPEN",
                        active_bill_key=str(item["bill_id"]),
                        level=item["level"],
                        strategy_code="AGING_V1",
                        lock_version=1,
                    )
                    created += 1
                case.active_bill_key = str(item["bill_id"])
                case.amount_snapshot = item["open_amount"]
                case.overdue_days = item["overdue_days"]
                case.effective_due_date = self._date(item["effective_due_date"])
                case.next_action_at = datetime.combine(day + timedelta(days=1), datetime.min.time())
                case.lock_version = int(case.lock_version or 1) + 1
                record_source = f"dunning:{day.isoformat()}:{item['bill_id']}:{item['level']}"
                if self.repo.record_by_source(record_source) is None:
                    self.repo.create_record(
                        case_id=int(case.id),
                        action_type="SYSTEM",
                        status="PLANNED",
                        channel="IN_APP",
                        note=f"AGING_V1 {item['level']} / {item['overdue_days']} days",
                        source_ref=record_source,
                        next_follow_up_at=case.next_action_at,
                        created_by=self.ctx.user_id,
                        created_at=utc_now(),
                    )
                self.work_items.ensure_from_source(
                    source_type="COLLECTION_CASE",
                    source_id=str(case.id),
                    item_type="COLLECTION_DUNNING",
                    title=f"{item['level']} 欠费催缴 / 账单 {item['bill_id']}",
                    park_id=item["park_id"],
                    priority="URGENT" if item["level"] in {"L3", "L4"} else "HIGH",
                    due_at=case.next_action_at.isoformat(),
                    commit=False,
                )
            summary = {
                "mode": "APPLY",
                "run_id": int(run.id),
                "as_of": day.isoformat(),
                "park_id": park_id,
                "total": len(items),
                "amount": str(money(sum(item["open_amount"] for item in items))),
                "created": created,
                "escalated": escalated,
                "unchanged": unchanged,
            }
            run.status = "COMPLETED"
            run.summary_json = summary
            complete_idempotent(
                self.session,
                tenant_id=self.ctx.tenant_id,
                operation="collection.dunning.apply",
                idem_key=idem,
                resource_type="DUNNING_RUN",
                resource_id=str(run.id),
                response=summary,
            )
            self.audit.record(
                action="run",
                resource_type="DUNNING_RUN",
                resource_id=run.id,
                park_id=park_id,
                detail={key: summary[key] for key in ("total", "created", "escalated")},
            )
            self.session.commit()
            return summary
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "自动催缴并发冲突", code="DUNNING_RUN_CONFLICT", status_code=409
            ) from exc

    def _adjustment_dict(self, row: Any) -> dict:
        approval_status = None
        if row.approval_id is not None:
            approval = self.approvals.get_by_id(int(row.approval_id))
            approval_status = approval.status if approval is not None else None
        return {
            "id": int(row.id),
            "park_id": int(row.park_id),
            "bill_id": int(row.bill_id),
            "adjustment_type": row.adjustment_type,
            "amount": str(money(row.amount)) if row.amount is not None else None,
            "requested_due_date": row.requested_due_date.isoformat()
            if row.requested_due_date
            else None,
            "reason": row.reason,
            "status": row.status,
            "approval_id": int(row.approval_id) if row.approval_id is not None else None,
            "approval_status": approval_status,
            "bill_lock_version_snapshot": row.bill_lock_version_snapshot,
            "open_amount_snapshot": str(money(row.open_amount_snapshot)),
            "lock_version": row.lock_version,
        }

    def request_adjustment(self, data: dict[str, Any], *, idempotency_key: str | None) -> dict:
        if not self.ctx.has_permission("receivable:adjust") or not self.ctx.has_permission(
            "approval:write"
        ):
            raise AppError("无应收调整申请权限", code="PERMISSION_DENIED", status_code=403)
        idem = normalize_idempotency_key(idempotency_key)
        if not idem:
            raise AppError("Idempotency-Key 必填", code="IDEMPOTENCY_KEY_REQUIRED", status_code=400)
        body_hash = request_hash(data)
        cached = begin_idempotent(
            self.session,
            tenant_id=self.ctx.tenant_id,
            user_id=self.ctx.user_id,
            operation="receivable.adjustment.request",
            idem_key=idem,
            body_hash=body_hash,
        )
        if cached is not None:
            if not self.ctx.allows_park(int(cached["park_id"])):
                raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
            return cached
        bill = self.bills.get_by_id(int(data["bill_id"]), for_update=True)
        if bill is None:
            raise AppError("账单不存在", code="BILL_NOT_FOUND", status_code=404)
        kind = str(data.get("adjustment_type") or "").strip().upper()
        if kind not in ADJUSTMENT_TYPES:
            raise AppError("调整类型无效", code="VALIDATION_ERROR", status_code=400)
        reason = str(data.get("reason") or "").strip()
        if not reason:
            raise AppError("调整原因必填", code="VALIDATION_ERROR", status_code=400)
        open_value = collectible_open_amount(
            bill.total_amount, bill.paid_amount, bill.waiver_amount, bill.bad_debt_amount
        )
        amount = money(data.get("amount") or 0) if kind in {"WAIVER", "BAD_DEBT"} else None
        requested_due = self._date(data["requested_due_date"]) if kind == "EXTENSION" else None
        if amount is not None and (amount <= 0 or amount > open_value):
            raise AppError(
                "调整金额超过可收余额", code="ADJUSTMENT_AMOUNT_INVALID", status_code=409
            )
        effective = effective_due_date(bill.due_date, bill.deferred_due_date)
        if kind == "EXTENSION" and (
            requested_due is None or effective is None or requested_due <= effective
        ):
            raise AppError(
                "延期日须晚于当前到期日", code="ADJUSTMENT_DUE_DATE_INVALID", status_code=400
            )
        if kind == "DISPUTE" and (bill.collection_hold or bill.dispute_status == "OPEN"):
            raise AppError("账单争议已开启", code="BILL_DISPUTE_ALREADY_OPEN", status_code=409)
        if kind == "DISPUTE_RESOLUTION" and (
            not bill.collection_hold or bill.dispute_status != "OPEN"
        ):
            raise AppError("账单没有待解决争议", code="BILL_DISPUTE_NOT_OPEN", status_code=409)
        row = self.repo.create_adjustment(
            park_id=int(bill.park_id),
            bill_id=int(bill.id),
            adjustment_type=kind,
            amount=amount,
            requested_due_date=requested_due,
            reason=reason,
            status="PENDING_APPROVAL",
            bill_lock_version_snapshot=int(bill.lock_version),
            open_amount_snapshot=open_value,
            idempotency_key=idem,
            lock_version=1,
            requested_by=self.ctx.user_id,
        )
        approval = self.approvals.create(
            park_id=int(bill.park_id),
            biz_type="RECEIVABLE_ADJUSTMENT",
            biz_id=str(row.id),
            title=f"应收{kind}审批 / {bill.bill_no}",
            applicant_user_id=self.ctx.user_id,
            remark=reason,
        )
        self.approvals.add_event(
            approval_id=int(approval.id),
            action="SUBMIT",
            actor_user_id=self.ctx.user_id,
            remark=reason,
        )
        row.approval_id = int(approval.id)
        self.work_items.ensure_from_source(
            source_type="RECEIVABLE_ADJUSTMENT",
            source_id=str(approval.id),
            item_type="RECEIVABLE_ADJUSTMENT_APPROVAL",
            title=f"应收{kind}待审批 / {bill.bill_no}",
            park_id=int(bill.park_id),
            priority="URGENT" if kind in {"WAIVER", "BAD_DEBT"} else "HIGH",
            commit=False,
        )
        self.audit.record(
            action="request",
            resource_type="RECEIVABLE_ADJUSTMENT",
            resource_id=row.id,
            park_id=bill.park_id,
            detail={"type": kind, "approval_id": approval.id},
        )
        response = self._adjustment_dict(row)
        complete_idempotent(
            self.session,
            tenant_id=self.ctx.tenant_id,
            operation="receivable.adjustment.request",
            idem_key=idem,
            resource_type="RECEIVABLE_ADJUSTMENT",
            resource_id=str(row.id),
            response=response,
        )
        self.session.commit()
        return response

    def list_adjustments(self, *, bill_id: int | None) -> list[dict]:
        if not self.ctx.has_permission("bill:read"):
            raise AppError("无应收查看权限", code="PERMISSION_DENIED", status_code=403)
        return [self._adjustment_dict(row) for row in self.repo.list_adjustments(bill_id=bill_id)]

    def apply_adjustment(self, adjustment_id: int, *, expected_version: int) -> dict:
        if not self.ctx.has_permission("receivable:adjust"):
            raise AppError("无应收调整权限", code="PERMISSION_DENIED", status_code=403)
        row = self.repo.adjustment(adjustment_id, for_update=True)
        if row is None:
            raise AppError("应收调整不存在", code="ADJUSTMENT_NOT_FOUND", status_code=404)
        if int(row.lock_version) != int(expected_version):
            raise AppError("应收调整版本冲突", code="ADJUSTMENT_VERSION_CONFLICT", status_code=409)
        if row.status == "APPLIED":
            return self._adjustment_dict(row)
        approval = self.approvals.get_by_id(int(row.approval_id or 0), for_update=True)
        if approval is None or approval.status != "APPROVED":
            raise AppError("应收调整尚未批准", code="ADJUSTMENT_APPROVAL_REQUIRED", status_code=409)
        bill = self.bills.get_by_id(int(row.bill_id), for_update=True)
        if bill is None:
            raise AppError("账单不存在", code="BILL_NOT_FOUND", status_code=404)
        current_open = collectible_open_amount(
            bill.total_amount, bill.paid_amount, bill.waiver_amount, bill.bad_debt_amount
        )
        if int(bill.lock_version) != int(row.bill_lock_version_snapshot) or current_open != money(
            row.open_amount_snapshot
        ):
            raise AppError("账单已变化，须重新申请", code="ADJUSTMENT_BILL_STALE", status_code=409)
        if row.adjustment_type == "WAIVER":
            bill.waiver_amount = money(Decimal(str(bill.waiver_amount)) + Decimal(str(row.amount)))
        elif row.adjustment_type == "BAD_DEBT":
            bill.bad_debt_amount = money(
                Decimal(str(bill.bad_debt_amount)) + Decimal(str(row.amount))
            )
        elif row.adjustment_type == "EXTENSION":
            bill.deferred_due_date = row.requested_due_date
        elif row.adjustment_type == "DISPUTE":
            bill.collection_hold = True
            bill.dispute_status = "OPEN"
        elif row.adjustment_type == "DISPUTE_RESOLUTION":
            bill.collection_hold = False
            bill.dispute_status = "RESOLVED"
        bill.lock_version += 1
        row.status = "APPLIED"
        row.applied_by = self.ctx.user_id
        row.applied_at = utc_now()
        row.lock_version += 1
        after_open = collectible_open_amount(
            bill.total_amount, bill.paid_amount, bill.waiver_amount, bill.bad_debt_amount
        )
        if after_open <= 0:
            for case in self.repo.active_cases_for_bill(int(bill.id), for_update=True):
                case.status = "CLOSED"
                case.active_bill_key = None
                case.resolution_code = "RECEIVABLE_SETTLED"
                case.closed_at = utc_now()
                case.lock_version += 1
                self.work_items.complete_by_source(
                    source_type="COLLECTION_CASE",
                    source_id=str(case.id),
                    item_type="COLLECTION_DUNNING",
                    commit=False,
                )
        self.work_items.complete_by_source(
            source_type="RECEIVABLE_ADJUSTMENT",
            source_id=str(row.approval_id),
            item_type="RECEIVABLE_ADJUSTMENT_APPROVAL",
            commit=False,
        )
        self.audit.record(
            action="apply",
            resource_type="RECEIVABLE_ADJUSTMENT",
            resource_id=row.id,
            park_id=bill.park_id,
            detail={"type": row.adjustment_type, "approval_id": row.approval_id},
        )
        self.session.commit()
        return {"adjustment": self._adjustment_dict(row), "bill_id": int(bill.id)}
