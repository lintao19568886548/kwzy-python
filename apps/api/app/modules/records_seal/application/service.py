"""Records, seal custody/use and truthful electronic-signature application service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.infrastructure.platform.number_sequence import next_number
from app.infrastructure.platform.providers import get_file_storage
from app.modules.records_seal.domain.rules import (
    access_mode,
    approval_submission_key,
    assert_category_confidentiality,
    bounded_text,
    canonical_payload_hash,
    enum_value,
    manifest_hash,
    retention_values,
    seal_kind,
    signature_adapter,
    signature_role,
    transition_seal,
)
from app.modules.records_seal.infrastructure.repository import RecordsSealRepository
from app.modules.workbench.application.work_item_service import WorkItemService
from app.modules.workflow.application.approval_service import ApprovalService
from app.shared.tenant_context import TenantContext

RECORD_STATUSES = {"DRAFT", "FILED", "ON_HOLD", "DISPOSITION_PENDING", "DISPOSED"}
APPROVAL_STATUS_MAP = {
    "PENDING": "PENDING_APPROVAL",
    "APPROVED": "APPROVED",
    "REJECTED": "REJECTED",
    "RETURNED": "APPROVAL_RETURNED",
    "WITHDRAWN": "WITHDRAWN",
}


def _naive_utc(value: Any, *, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400) from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise AppError(f"{field} 无效", code="VALIDATION_ERROR", status_code=400)
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _expected(row, value: Any) -> None:  # type: ignore[no-untyped-def]
    if int(row.lock_version) != int(value):
        raise AppError("数据已被其他操作更新", code="VERSION_CONFLICT", status_code=409)


class RecordsSealService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = RecordsSealRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)
        self.approvals = ApprovalService(session, ctx)
        self.work_items = WorkItemService(session, ctx)
        settings = get_settings()
        self.storage = get_file_storage(
            app_env=settings.app_env,
            provider=settings.oss_provider,
            local_root=settings.oss_local_root,
            endpoint=settings.oss_endpoint,
            bucket=settings.oss_bucket,
            access_key=settings.oss_access_key,
            secret_key=settings.oss_secret_key,
        )

    def _permission(self, *codes: str) -> None:
        if any(self.ctx.has_permission(code) for code in codes):
            return
        raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def _tenant_level(self) -> None:
        if not self.ctx.has_all_park_access:
            raise AppError("无租户级数据访问范围", code="PARK_SCOPE_DENIED", status_code=403)

    def _park(self, value: Any | None) -> int | None:
        if value is None:
            self._tenant_level()
            return None
        park_id = int(value)
        if not self.repo.park_exists(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(park_id):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        return park_id

    def _user(self, value: Any, *, park_id: int | None) -> int:
        user_id = int(value)
        if self.repo.active_user(user_id, park_id) is None:
            raise AppError("用户不存在或无该园区范围", code="USER_SCOPE_INVALID", status_code=404)
        return user_id

    def _commit(self, *, code: str, message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    def _require_category(self, category_id: int, *, for_update: bool = False):
        row = self.repo.get_category(category_id, for_update=for_update)
        if row is None:
            raise AppError("档案分类不存在", code="RECORD_CATEGORY_NOT_FOUND", status_code=404)
        return row

    def _require_record(self, record_id: int, *, for_update: bool = False):
        row = self.repo.get_record(record_id, for_update=for_update)
        if row is None:
            raise AppError("档案不存在", code="RECORD_NOT_FOUND", status_code=404)
        return row

    def _require_revision(self, revision_id: int):
        row = self.repo.get_revision(revision_id)
        if row is None:
            raise AppError("档案版本不存在", code="RECORD_REVISION_NOT_FOUND", status_code=404)
        return row

    # Classification and record files
    @staticmethod
    def _category_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "code": row.code,
            "name": row.name,
            "retention_mode": row.retention_mode,
            "retention_years": row.retention_years,
            "confidentiality_max": row.confidentiality_max,
            "status": row.status,
            "lock_version": int(row.lock_version),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def list_categories(self, *, include_retired: bool) -> list[dict[str, Any]]:
        self._permission("record:read", "record:manage")
        return [
            self._category_dict(row)
            for row in self.repo.list_categories(include_retired=include_retired)
        ]

    def create_category(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:manage")
        self._tenant_level()
        mode, years, _ = retention_values(
            mode=data["retention_mode"],
            years=data.get("retention_years"),
            filed_on=utc_now().date(),
        )
        row = self.repo.create_category(
            code=bounded_text(data.get("code"), field="code", maximum=32, required=True).upper(),
            name=bounded_text(data.get("name"), field="name", maximum=128, required=True),
            retention_mode=mode,
            retention_years=years,
            confidentiality_max=assert_category_confidentiality(
                category_max="RESTRICTED", requested=data["confidentiality_max"]
            ),
            status="ACTIVE",
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="create",
            resource_type="RECORD_CATEGORY",
            resource_id=row.id,
            detail={"code": row.code, "retention_mode": row.retention_mode},
        )
        self._commit(code="RECORD_CATEGORY_CONFLICT", message="档案分类编码冲突")
        return self._category_dict(row)

    def update_category(self, category_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:manage")
        self._tenant_level()
        row = self._require_category(category_id, for_update=True)
        _expected(row, data["expected_version"])
        if row.status != "ACTIVE":
            raise AppError(
                "已停用分类不可修改", code="RECORD_CATEGORY_STATE_INVALID", status_code=409
            )
        if "name" in data:
            row.name = bounded_text(data.get("name"), field="name", maximum=128, required=True)
        if "retention_mode" in data or "retention_years" in data:
            target_mode = data.get("retention_mode", row.retention_mode)
            target_years = data.get("retention_years", row.retention_years)
            if str(target_mode).strip().upper() == "PERMANENT" and "retention_years" not in data:
                target_years = None
            mode, years, _ = retention_values(
                mode=target_mode,
                years=target_years,
                filed_on=utc_now().date(),
            )
            row.retention_mode, row.retention_years = mode, years
        if "confidentiality_max" in data:
            row.confidentiality_max = assert_category_confidentiality(
                category_max="RESTRICTED", requested=data["confidentiality_max"]
            )
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="update",
            resource_type="RECORD_CATEGORY",
            resource_id=row.id,
            detail={"reason": data["reason"], "version": row.lock_version},
        )
        self._commit(code="RECORD_CATEGORY_CONFLICT", message="档案分类更新冲突")
        return self._category_dict(row)

    def retire_category(self, category_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:manage")
        self._tenant_level()
        row = self._require_category(category_id, for_update=True)
        _expected(row, data["expected_version"])
        if self.repo.category_record_count(category_id):
            raise AppError("分类仍有未处置档案", code="RECORD_CATEGORY_IN_USE", status_code=409)
        row.status = "RETIRED"
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="retire",
            resource_type="RECORD_CATEGORY",
            resource_id=row.id,
            detail={"reason": data["reason"]},
        )
        self._commit(code="RECORD_CATEGORY_CONFLICT", message="档案分类停用冲突")
        return self._category_dict(row)

    @staticmethod
    def _revision_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "record_id": int(row.record_id),
            "attachment_id": int(row.attachment_id),
            "version_no": int(row.version_no),
            "filename": row.filename,
            "content_type": row.content_type,
            "size_bytes": int(row.size_bytes),
            "checksum_sha256": row.checksum_sha256,
            "status": row.status,
            "supersedes_revision_id": row.supersedes_revision_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _record_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = {
            "id": int(row.id),
            "park_id": int(row.park_id) if row.park_id is not None else None,
            "category_id": int(row.category_id),
            "record_no": row.record_no,
            "title": row.title,
            "description": row.description,
            "confidentiality": row.confidentiality,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "status": row.status,
            "retention_mode": row.retention_mode,
            "retention_years": row.retention_years,
            "retention_until": row.retention_until.isoformat() if row.retention_until else None,
            "filed_at": row.filed_at.isoformat() if row.filed_at else None,
            "disposed_at": row.disposed_at.isoformat() if row.disposed_at else None,
            "lock_version": int(row.lock_version),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        if detail:
            result["revisions"] = [
                self._revision_dict(item) for item in self.repo.revisions(int(row.id))
            ]
            result["holds"] = [
                {
                    "id": int(item.id),
                    "status": item.status,
                    "reason": item.reason,
                    "placed_by": item.placed_by,
                    "placed_at": item.placed_at.isoformat(),
                    "released_by": item.released_by,
                    "released_at": item.released_at.isoformat() if item.released_at else None,
                    "release_reason": item.release_reason,
                }
                for item in self.repo.holds(int(row.id))
            ]
            result["integrity_events"] = [
                {
                    "id": int(item.id),
                    "revision_id": int(item.revision_id),
                    "result": item.result,
                    "expected_checksum": item.expected_checksum,
                    "actual_checksum": item.actual_checksum,
                    "detail": item.detail,
                    "verified_at": item.verified_at.isoformat(),
                }
                for item in self.repo.integrity_events(int(row.id))
            ]
        return result

    def list_records(
        self,
        *,
        page: int,
        page_size: int,
        park_id: int | None,
        category_id: int | None,
        status: str | None,
        keyword: str | None,
    ) -> dict[str, Any]:
        self._permission("record:read")
        if park_id is not None:
            self._park(park_id)
        normalized_status = (
            enum_value(status, field="status", allowed=RECORD_STATUSES) if status else None
        )
        normalized_keyword = bounded_text(keyword, field="keyword", maximum=100) or None
        rows = self.repo.list_records(
            offset=(page - 1) * page_size,
            limit=page_size,
            park_id=park_id,
            category_id=category_id,
            status=normalized_status,
            keyword=normalized_keyword,
        )
        return {
            "items": [self._record_dict(row) for row in rows],
            "total": self.repo.count_records(
                park_id=park_id,
                category_id=category_id,
                status=normalized_status,
                keyword=normalized_keyword,
            ),
            "page": page,
            "page_size": page_size,
        }

    def get_record(self, record_id: int) -> dict[str, Any]:
        self._permission("record:read")
        return self._record_dict(self._require_record(record_id), detail=True)

    def create_record(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:write")
        category = self._require_category(int(data["category_id"]))
        if category.status != "ACTIVE":
            raise AppError("档案分类已停用", code="RECORD_CATEGORY_STATE_INVALID", status_code=409)
        park_id = self._park(data.get("park_id"))
        now = utc_now()
        mode, years, retention_until = retention_values(
            mode=category.retention_mode,
            years=category.retention_years,
            filed_on=now.date(),
        )
        sequence = next_number(
            self.session,
            tenant_id=self.ctx.tenant_id,
            biz_type="RECORD",
            period_key=now.strftime("%Y"),
        )
        row = self.repo.create_record(
            park_id=park_id,
            category_id=int(category.id),
            record_no=f"REC-{now:%Y}-{sequence:06d}",
            title=bounded_text(data.get("title"), field="title", maximum=255, required=True),
            description=bounded_text(data.get("description"), field="description", maximum=5000)
            or None,
            confidentiality=assert_category_confidentiality(
                category_max=category.confidentiality_max, requested=data["confidentiality"]
            ),
            source_type=bounded_text(
                data.get("source_type"), field="source_type", maximum=64, required=True
            ).upper(),
            source_id=bounded_text(
                data.get("source_id"), field="source_id", maximum=64, required=True
            ),
            status="DRAFT",
            retention_mode=mode,
            retention_years=years,
            retention_until=retention_until,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.audit.record(
            action="create",
            resource_type="RECORD_FILE",
            resource_id=row.id,
            park_id=park_id,
            detail={"record_no": row.record_no, "source_type": row.source_type},
        )
        self._commit(code="RECORD_CONFLICT", message="档案编号或来源冲突")
        return self._record_dict(row, detail=True)

    def add_revision(self, record_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:write")
        record = self._require_record(record_id, for_update=True)
        _expected(record, data["expected_version"])
        if record.status in {"DISPOSITION_PENDING", "DISPOSED"}:
            raise AppError("当前档案状态不可新增版本", code="RECORD_STATE_INVALID", status_code=409)
        attachment = self.repo.get_attachment(int(data["attachment_id"]))
        if attachment is None:
            raise AppError("附件不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
        if attachment.park_id != record.park_id:
            raise AppError("附件与档案园区不匹配", code="ATTACHMENT_PARK_MISMATCH", status_code=409)
        try:
            content = self.storage.get_bytes(attachment.object_key)
        except Exception as exc:
            raise AppError(
                "附件内容不可用",
                code="ATTACHMENT_CONTENT_UNAVAILABLE",
                status_code=503,
            ) from exc
        actual_size = len(content)
        if actual_size != int(attachment.size_bytes):
            raise AppError(
                "附件大小校验失败", code="ATTACHMENT_INTEGRITY_MISMATCH", status_code=409
            )
        latest = self.repo.latest_revision(record_id)
        row = self.repo.create_revision(
            park_id=record.park_id,
            record_id=int(record.id),
            attachment_id=int(attachment.id),
            version_no=int(latest.version_no) + 1 if latest else 1,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size_bytes=actual_size,
            checksum_sha256=sha256(content).hexdigest(),
            status="ACTIVE",
            supersedes_revision_id=int(latest.id) if latest else None,
            created_by=self.ctx.user_id or None,
        )
        record.lock_version = int(record.lock_version) + 1
        self.repo.save(record)
        self.audit.record(
            action="add_revision",
            resource_type="RECORD_FILE",
            resource_id=record.id,
            park_id=record.park_id,
            detail={"revision_id": row.id, "checksum_sha256": row.checksum_sha256},
        )
        self._commit(code="RECORD_REVISION_CONFLICT", message="档案版本并发冲突")
        return self._record_dict(record, detail=True)

    def file_record(self, record_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:write")
        record = self._require_record(record_id, for_update=True)
        _expected(record, data["expected_version"])
        if record.status != "DRAFT":
            raise AppError("仅草稿档案可归档", code="RECORD_STATE_INVALID", status_code=409)
        if self.repo.latest_revision(record_id) is None:
            raise AppError(
                "归档前必须上传至少一个版本", code="RECORD_REVISION_REQUIRED", status_code=409
            )
        now = utc_now()
        mode, years, retention_until = retention_values(
            mode=record.retention_mode, years=record.retention_years, filed_on=now.date()
        )
        record.status = "FILED"
        record.retention_mode = mode
        record.retention_years = years
        record.retention_until = retention_until
        record.filed_at = now
        record.filed_by = self.ctx.user_id or None
        record.lock_version = int(record.lock_version) + 1
        self.repo.save(record)
        self.audit.record(
            action="file",
            resource_type="RECORD_FILE",
            resource_id=record.id,
            park_id=record.park_id,
            detail={"reason": data["reason"], "retention_until": str(retention_until)},
        )
        self._commit(code="RECORD_FILE_CONFLICT", message="档案归档并发冲突")
        return self._record_dict(record, detail=True)

    def verify_integrity(
        self, record_id: int, data: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._permission("record:verify")
        record = self._require_record(record_id)
        revision = (
            self._require_revision(int(data["revision_id"]))
            if data.get("revision_id")
            else self.repo.latest_revision(record_id)
        )
        if revision is None or int(revision.record_id) != int(record.id):
            raise AppError("档案版本不存在", code="RECORD_REVISION_NOT_FOUND", status_code=404)
        previous = self.repo.integrity_by_key(idempotency_key)
        if previous is not None:
            if int(previous.record_id) != int(record_id) or int(previous.revision_id) != int(
                revision.id
            ):
                raise AppError("幂等键请求内容不一致", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return {
                "id": int(previous.id),
                "record_id": int(previous.record_id),
                "revision_id": int(previous.revision_id),
                "result": previous.result,
                "expected_checksum": previous.expected_checksum,
                "actual_checksum": previous.actual_checksum,
                "detail": previous.detail,
            }
        attachment = self.repo.get_attachment(int(revision.attachment_id))
        actual: str | None = None
        result = "UNAVAILABLE"
        detail = "attachment metadata or object unavailable"
        if attachment is not None:
            try:
                actual = sha256(self.storage.get_bytes(attachment.object_key)).hexdigest()
                result = "MATCH" if actual == revision.checksum_sha256 else "MISMATCH"
                detail = (
                    "content checksum matched" if result == "MATCH" else "content checksum mismatch"
                )
            except (FileNotFoundError, LookupError, OSError, RuntimeError):
                detail = "attachment object unavailable"
        event = self.repo.create_integrity_event(
            park_id=record.park_id,
            record_id=int(record.id),
            revision_id=int(revision.id),
            result=result,
            expected_checksum=revision.checksum_sha256,
            actual_checksum=actual,
            detail=detail,
            idempotency_key=idempotency_key,
            verified_by=self.ctx.user_id or None,
            verified_at=utc_now(),
        )
        self.audit.record(
            action="verify_integrity",
            resource_type="RECORD_FILE",
            resource_id=record.id,
            park_id=record.park_id,
            detail={"revision_id": revision.id, "result": result},
        )
        self._commit(code="RECORD_VERIFY_CONFLICT", message="完整性校验幂等冲突")
        return {
            "id": int(event.id),
            "record_id": int(event.record_id),
            "revision_id": int(event.revision_id),
            "result": event.result,
            "expected_checksum": event.expected_checksum,
            "actual_checksum": event.actual_checksum,
            "detail": event.detail,
        }

    # Legal holds, access and disposition
    def place_hold(self, record_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:hold")
        record = self._require_record(record_id, for_update=True)
        _expected(record, data["expected_version"])
        if record.status not in {"FILED", "ON_HOLD"}:
            raise AppError("当前档案状态不可设置保全", code="RECORD_STATE_INVALID", status_code=409)
        existing = self.repo.active_hold(record_id)
        if existing is not None:
            raise AppError("档案已处于保全状态", code="RECORD_HOLD_EXISTS", status_code=409)
        now = utc_now()
        hold = self.repo.create_hold(
            park_id=record.park_id,
            record_id=int(record.id),
            status="ACTIVE",
            reason=bounded_text(data["reason"], field="reason", maximum=1000, required=True),
            placed_by=self.ctx.user_id or None,
            placed_at=now,
        )
        record.status = "ON_HOLD"
        record.lock_version = int(record.lock_version) + 1
        self.repo.save(record)
        self.audit.record(
            action="place_hold",
            resource_type="RECORD_FILE",
            resource_id=record.id,
            park_id=record.park_id,
            detail={"hold_id": hold.id, "reason": hold.reason},
        )
        self._commit(code="RECORD_HOLD_CONFLICT", message="档案保全并发冲突")
        return self._record_dict(record, detail=True)

    def release_hold(self, record_id: int, hold_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:hold")
        record = self._require_record(record_id, for_update=True)
        _expected(record, data["expected_version"])
        hold = self.repo.get_hold(hold_id)
        if hold is None or int(hold.record_id) != int(record.id) or hold.status != "ACTIVE":
            raise AppError("生效保全记录不存在", code="RECORD_HOLD_NOT_FOUND", status_code=404)
        hold.status = "RELEASED"
        hold.released_by = self.ctx.user_id or None
        hold.released_at = utc_now()
        hold.release_reason = bounded_text(
            data["reason"], field="reason", maximum=1000, required=True
        )
        self.repo.save(hold)
        record.status = "FILED"
        record.lock_version = int(record.lock_version) + 1
        self.repo.save(record)
        self.audit.record(
            action="release_hold",
            resource_type="RECORD_FILE",
            resource_id=record.id,
            park_id=record.park_id,
            detail={"hold_id": hold.id, "reason": hold.release_reason},
        )
        self._commit(code="RECORD_HOLD_CONFLICT", message="档案保全释放冲突")
        return self._record_dict(record, detail=True)

    def _create_approval(
        self,
        *,
        row,
        biz_type: str,
        definition_code: str,
        request_key: str,
        title: str,
        park_id: int | None,
        snapshot: dict[str, Any],
    ) -> None:  # type: ignore[no-untyped-def]
        existing = self.repo.approval_by_business(biz_type, str(row.id))
        if existing is None:
            approval = self.approvals.create(
                {
                    "biz_type": biz_type,
                    "biz_id": str(row.id),
                    "title": title,
                    "park_id": park_id,
                    "definition_code": definition_code,
                    "idempotency_key": approval_submission_key(
                        biz_type=biz_type, request_key=request_key
                    ),
                    "priority": "HIGH",
                    "snapshot": snapshot,
                }
            )
            approval_id = int(approval["id"])
        else:
            approval_id = int(existing.id)
        row.approval_id = approval_id
        self.repo.save(row)
        self.session.commit()

    @staticmethod
    def _approval_state(approval) -> str:  # type: ignore[no-untyped-def]
        if approval is None:
            raise AppError("审批关联缺失", code="APPROVAL_LINK_MISSING", status_code=409)
        return APPROVAL_STATUS_MAP.get(str(approval.status), "PENDING_APPROVAL")

    @staticmethod
    def _access_dict(row, approval=None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "record_id": int(row.record_id),
            "park_id": row.park_id,
            "mode": row.mode,
            "purpose": row.purpose,
            "requested_until": row.requested_until.isoformat(),
            "requester_user_id": int(row.requester_user_id),
            "approval_id": row.approval_id,
            "approval_status": approval.status if approval else None,
            "status": row.status,
            "checked_out_at": row.checked_out_at.isoformat() if row.checked_out_at else None,
            "returned_at": row.returned_at.isoformat() if row.returned_at else None,
            "lock_version": int(row.lock_version),
        }

    def request_access(
        self, record_id: int, data: dict[str, Any], *, request_key: str
    ) -> dict[str, Any]:
        self._permission("record:access_request")
        previous = self.repo.access_by_key(request_key)
        if previous is not None:
            if int(previous.record_id) != int(record_id):
                raise AppError("幂等键已用于其他申请", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._access_dict(previous, self.repo.approval(previous.approval_id))
        record = self._require_record(record_id)
        if record.status not in {"FILED", "ON_HOLD"}:
            raise AppError("仅已归档档案可申请访问", code="RECORD_STATE_INVALID", status_code=409)
        until = _naive_utc(data["requested_until"], field="requested_until")
        if until <= utc_now():
            raise AppError("访问截止时间必须晚于当前时间", code="VALIDATION_ERROR", status_code=400)
        row = self.repo.create_access_request(
            park_id=record.park_id,
            record_id=int(record.id),
            mode=access_mode(data["mode"]),
            purpose=bounded_text(data["purpose"], field="purpose", maximum=1000, required=True),
            requested_until=until,
            requester_user_id=self.ctx.user_id,
            status="PENDING_APPROVAL",
            request_key=request_key,
            lock_version=1,
        )
        self._create_approval(
            row=row,
            biz_type="RECORD_ACCESS",
            definition_code=data["definition_code"],
            request_key=request_key,
            title=f"档案访问申请：{record.record_no}",
            park_id=record.park_id,
            snapshot={
                "record_id": record.id,
                "record_no": record.record_no,
                "mode": row.mode,
                "requested_until": until.isoformat(),
            },
        )
        self.audit.record(
            action="request_access",
            resource_type="RECORD_FILE",
            resource_id=record.id,
            park_id=record.park_id,
            detail={"access_request_id": row.id, "mode": row.mode},
        )
        self.session.commit()
        return self._access_dict(row, self.repo.approval(row.approval_id))

    def list_access_requests(self, *, status: str | None) -> list[dict[str, Any]]:
        self._permission("record:access_review", "record:access_request")
        return [
            self._access_dict(row, self.repo.approval(row.approval_id))
            for row in self.repo.list_access_requests(status=status)
        ]

    def refresh_access(self, request_id: int) -> dict[str, Any]:
        self._permission("record:access_review", "record:access_request")
        row = self.repo.get_access_request(request_id, for_update=True)
        if row is None:
            raise AppError("档案访问申请不存在", code="RECORD_ACCESS_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if row.status in {"PENDING_APPROVAL", "APPROVAL_RETURNED"}:
            row.status = self._approval_state(approval)
            row.lock_version = int(row.lock_version) + 1
            self.repo.save(row)
            self.session.commit()
        return self._access_dict(row, approval)

    def checkout_access(self, request_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:access_execute")
        row = self.repo.get_access_request(request_id, for_update=True)
        if row is None:
            raise AppError("档案访问申请不存在", code="RECORD_ACCESS_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        row.status = self._approval_state(self.repo.approval(row.approval_id))
        if row.mode != "BORROW" or row.status != "APPROVED":
            raise AppError(
                "仅审批通过的借阅申请可出库", code="RECORD_ACCESS_STATE_INVALID", status_code=409
            )
        if row.requested_until <= utc_now():
            row.status = "EXPIRED"
            row.lock_version = int(row.lock_version) + 1
            self.repo.save(row)
            self.session.commit()
            raise AppError("借阅申请已过期", code="RECORD_ACCESS_EXPIRED", status_code=409)
        row.status = "CHECKED_OUT"
        row.checked_out_at = utc_now()
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="checkout",
            resource_type="RECORD_ACCESS",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"record_id": row.record_id, "reason": data["reason"]},
        )
        self._commit(code="RECORD_ACCESS_CONFLICT", message="借阅出库并发冲突")
        return self._access_dict(row, self.repo.approval(row.approval_id))

    def return_access(self, request_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:access_execute")
        row = self.repo.get_access_request(request_id, for_update=True)
        if row is None:
            raise AppError("档案访问申请不存在", code="RECORD_ACCESS_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        if row.status != "CHECKED_OUT":
            raise AppError(
                "档案未处于借出状态", code="RECORD_ACCESS_STATE_INVALID", status_code=409
            )
        row.status = "RETURNED"
        row.returned_at = utc_now()
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="return",
            resource_type="RECORD_ACCESS",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"record_id": row.record_id, "reason": data["reason"]},
        )
        self._commit(code="RECORD_ACCESS_CONFLICT", message="档案归还并发冲突")
        return self._access_dict(row, self.repo.approval(row.approval_id))

    @staticmethod
    def _disposition_dict(row, approval=None, confirmations=()) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "record_id": int(row.record_id),
            "park_id": row.park_id,
            "reason": row.reason,
            "requested_by": int(row.requested_by),
            "approval_id": row.approval_id,
            "approval_status": approval.status if approval else None,
            "status": row.status,
            "manifest_sha256": row.manifest_sha256,
            "storage_deletion_status": row.storage_deletion_status,
            "disposed_at": row.disposed_at.isoformat() if row.disposed_at else None,
            "lock_version": int(row.lock_version),
            "confirmations": [
                {
                    "id": int(item.id),
                    "confirmer_user_id": int(item.confirmer_user_id),
                    "reason": item.reason,
                    "confirmed_at": item.confirmed_at.isoformat(),
                }
                for item in confirmations
            ],
        }

    def request_disposition(
        self, record_id: int, data: dict[str, Any], *, request_key: str
    ) -> dict[str, Any]:
        self._permission("record:dispose_request")
        previous = self.repo.disposition_by_key(request_key)
        if previous is not None:
            if int(previous.record_id) != int(record_id):
                raise AppError("幂等键已用于其他处置", code="IDEMPOTENCY_CONFLICT", status_code=409)
            return self._disposition_dict(
                previous,
                self.repo.approval(previous.approval_id),
                self.repo.disposition_confirmations(previous.id),
            )
        record = self._require_record(record_id, for_update=True)
        _expected(record, data["expected_version"])
        if record.status != "FILED":
            raise AppError(
                "仅已归档且未保全档案可申请处置", code="RECORD_STATE_INVALID", status_code=409
            )
        if record.retention_mode == "PERMANENT" or not record.retention_until:
            raise AppError("永久档案不可处置", code="RECORD_PERMANENT", status_code=409)
        if record.retention_until > utc_now().date():
            raise AppError("档案尚未达到处置日期", code="RECORD_RETENTION_ACTIVE", status_code=409)
        if self.repo.active_hold(record.id) is not None:
            raise AppError("档案处于保全状态", code="RECORD_HOLD_ACTIVE", status_code=409)
        row = self.repo.create_disposition(
            park_id=record.park_id,
            record_id=int(record.id),
            reason=bounded_text(data["reason"], field="reason", maximum=1000, required=True),
            requested_by=self.ctx.user_id,
            status="PENDING_APPROVAL",
            request_key=request_key,
            storage_deletion_status="NOT_EXECUTED",
            lock_version=1,
        )
        record.status = "DISPOSITION_PENDING"
        record.lock_version = int(record.lock_version) + 1
        self.repo.save(record)
        self._create_approval(
            row=row,
            biz_type="RECORD_DISPOSITION",
            definition_code=data["definition_code"],
            request_key=request_key,
            title=f"档案处置申请：{record.record_no}",
            park_id=record.park_id,
            snapshot={
                "record_id": record.id,
                "record_no": record.record_no,
                "retention_until": record.retention_until.isoformat(),
                "reason": row.reason,
            },
        )
        self.audit.record(
            action="request_disposition",
            resource_type="RECORD_FILE",
            resource_id=record.id,
            park_id=record.park_id,
            detail={"disposition_id": row.id},
        )
        self.session.commit()
        return self._disposition_dict(row, self.repo.approval(row.approval_id), ())

    def list_dispositions(self, *, status: str | None) -> list[dict[str, Any]]:
        self._permission("record:dispose_review", "record:dispose_request")
        return [
            self._disposition_dict(
                row,
                self.repo.approval(row.approval_id),
                self.repo.disposition_confirmations(row.id),
            )
            for row in self.repo.list_dispositions(status=status)
        ]

    def refresh_disposition(self, disposition_id: int) -> dict[str, Any]:
        self._permission("record:dispose_review", "record:dispose_request")
        row = self.repo.get_disposition(disposition_id, for_update=True)
        if row is None:
            raise AppError(
                "档案处置申请不存在", code="RECORD_DISPOSITION_NOT_FOUND", status_code=404
            )
        approval = self.repo.approval(row.approval_id)
        if row.status in {"PENDING_APPROVAL", "APPROVAL_RETURNED"}:
            row.status = self._approval_state(approval)
            if row.status == "APPROVED":
                row.status = "CONFIRMING"
                self.work_items.ensure_from_source(
                    source_type="RECORD_DISPOSITION",
                    source_id=str(row.id),
                    item_type="RECORD_DISPOSITION_CONFIRM",
                    title="档案处置双人确认",
                    description="审批已通过，需两名非申请人分别确认；只执行逻辑处置。",
                    park_id=row.park_id,
                    priority="HIGH",
                    deep_link=f"/records-seal/dispositions/{row.id}",
                    commit=False,
                )
            row.lock_version = int(row.lock_version) + 1
            self.repo.save(row)
            self.session.commit()
        return self._disposition_dict(row, approval, self.repo.disposition_confirmations(row.id))

    def confirm_disposition(self, disposition_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("record:dispose_confirm")
        row = self.repo.get_disposition(disposition_id, for_update=True)
        if row is None:
            raise AppError(
                "档案处置申请不存在", code="RECORD_DISPOSITION_NOT_FOUND", status_code=404
            )
        _expected(row, data["expected_version"])
        if row.status != "CONFIRMING":
            raise AppError(
                "处置申请尚未进入确认阶段", code="RECORD_DISPOSITION_STATE_INVALID", status_code=409
            )
        if int(row.requested_by) == int(self.ctx.user_id):
            raise AppError(
                "申请人不得参与处置确认", code="RECORD_DISPOSITION_SELF_CONFIRM", status_code=403
            )
        approval = self.repo.approval(row.approval_id)
        if approval is None or approval.status != "APPROVED":
            raise AppError("处置审批未通过", code="APPROVAL_NOT_APPROVED", status_code=409)
        if int(approval.approver_user_id or 0) == int(row.requested_by):
            raise AppError(
                "处置审批违反职责分离", code="APPROVAL_SELF_DECISION_INVALID", status_code=409
            )
        self.repo.create_disposition_confirmation(
            disposition_id=int(row.id),
            confirmer_user_id=self.ctx.user_id,
            reason=bounded_text(data["reason"], field="reason", maximum=1000, required=True),
            confirmed_at=utc_now(),
        )
        confirmations = list(self.repo.disposition_confirmations(row.id))
        row.lock_version = int(row.lock_version) + 1
        if len(confirmations) >= 2:
            record = self._require_record(int(row.record_id), for_update=True)
            revisions = list(self.repo.revisions(record.id))
            row.manifest_sha256 = manifest_hash(
                [
                    {
                        "id": item.id,
                        "attachment_id": item.attachment_id,
                        "checksum_sha256": item.checksum_sha256,
                        "size_bytes": item.size_bytes,
                    }
                    for item in revisions
                ]
            )
            row.storage_deletion_status = "RETAINED_LOGICAL_ONLY"
            row.status = "DISPOSED"
            row.disposed_at = utc_now()
            record.status = "DISPOSED"
            record.disposed_at = row.disposed_at
            record.disposed_by = self.ctx.user_id or None
            record.lock_version = int(record.lock_version) + 1
            self.repo.save(record)
            for revision in revisions:
                revision.status = "DISPOSED"
                self.repo.save(revision)
            self.work_items.complete_by_source(
                source_type="RECORD_DISPOSITION",
                source_id=str(row.id),
                item_type="RECORD_DISPOSITION_CONFIRM",
                commit=False,
            )
        self.repo.save(row)
        self.audit.record(
            action="confirm_disposition",
            resource_type="RECORD_DISPOSITION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "confirmation_count": len(confirmations),
                "status": row.status,
                "storage_deletion_status": row.storage_deletion_status,
            },
        )
        self._commit(code="RECORD_DISPOSITION_CONFLICT", message="处置确认并发冲突")
        return self._disposition_dict(row, approval, confirmations)

    # Seal custody and use
    @staticmethod
    def _custody_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "event_type": row.event_type,
            "status": row.status,
            "from_custodian_user_id": row.from_custodian_user_id,
            "to_custodian_user_id": row.to_custodian_user_id,
            "actor_user_id": row.actor_user_id,
            "reason": row.reason,
            "occurred_at": row.occurred_at.isoformat(),
        }

    def _seal_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = {
            "id": int(row.id),
            "park_id": int(row.park_id) if row.park_id is not None else None,
            "seal_code": row.seal_code,
            "name": row.name,
            "kind": row.kind,
            "status": row.status,
            "custodian_user_id": int(row.custodian_user_id),
            "description": row.description,
            "lock_version": int(row.lock_version),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        if detail:
            result["custody_events"] = [
                self._custody_dict(item) for item in self.repo.custody_events(row.id)
            ]
        return result

    def list_seals(self, *, park_id: int | None, status: str | None) -> list[dict[str, Any]]:
        self._permission("seal:read")
        if park_id is not None:
            self._park(park_id)
        return [
            self._seal_dict(row) for row in self.repo.list_seals(park_id=park_id, status=status)
        ]

    def get_seal(self, seal_id: int) -> dict[str, Any]:
        self._permission("seal:read")
        row = self.repo.get_seal(seal_id)
        if row is None:
            raise AppError("印章不存在", code="SEAL_NOT_FOUND", status_code=404)
        return self._seal_dict(row, detail=True)

    def create_seal(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("seal:manage")
        park_id = self._park(data.get("park_id"))
        custodian = self._user(data["custodian_user_id"], park_id=park_id)
        row = self.repo.create_seal(
            park_id=park_id,
            seal_code=bounded_text(
                data["seal_code"], field="seal_code", maximum=32, required=True
            ).upper(),
            name=bounded_text(data["name"], field="name", maximum=128, required=True),
            kind=seal_kind(data["kind"]),
            status="ACTIVE",
            custodian_user_id=custodian,
            description=bounded_text(data.get("description"), field="description", maximum=1000)
            or None,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        self.repo.create_custody_event(
            park_id=park_id,
            seal_id=row.id,
            event_type="CREATED",
            status="COMPLETED",
            to_custodian_user_id=custodian,
            actor_user_id=self.ctx.user_id or None,
            reason="创建印章台账",
            occurred_at=utc_now(),
        )
        self.audit.record(
            action="create",
            resource_type="SEAL_ASSET",
            resource_id=row.id,
            park_id=park_id,
            detail={"seal_code": row.seal_code, "kind": row.kind},
        )
        self._commit(code="SEAL_CONFLICT", message="印章编码冲突")
        return self._seal_dict(row, detail=True)

    def transfer_seal(self, seal_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("seal:custody")
        row = self.repo.get_seal(seal_id, for_update=True)
        if row is None:
            raise AppError("印章不存在", code="SEAL_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        if int(row.custodian_user_id) != int(self.ctx.user_id) and not self.ctx.has_permission(
            "seal:manage"
        ):
            raise AppError("仅当前保管人可发起移交", code="SEAL_CUSTODY_DENIED", status_code=403)
        target = self._user(data["to_custodian_user_id"], park_id=row.park_id)
        if target == int(row.custodian_user_id):
            raise AppError("不可移交给当前保管人", code="VALIDATION_ERROR", status_code=400)
        row.status = transition_seal(row.status, "TRANSFER_PENDING")
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        event = self.repo.create_custody_event(
            park_id=row.park_id,
            seal_id=row.id,
            event_type="TRANSFER_REQUESTED",
            status="PENDING",
            from_custodian_user_id=row.custodian_user_id,
            to_custodian_user_id=target,
            actor_user_id=self.ctx.user_id or None,
            reason=bounded_text(data["reason"], field="reason", maximum=1000, required=True),
            occurred_at=utc_now(),
        )
        self.work_items.ensure_from_source(
            source_type="SEAL_TRANSFER",
            source_id=str(event.id),
            item_type="SEAL_TRANSFER_ACCEPT",
            title=f"接收印章：{row.name}",
            park_id=row.park_id,
            priority="HIGH",
            assignee_user_id=target,
            deep_link=f"/records-seal/seals/{row.id}",
            commit=False,
        )
        self.audit.record(
            action="transfer_request",
            resource_type="SEAL_ASSET",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"from": row.custodian_user_id, "to": target},
        )
        self._commit(code="SEAL_TRANSFER_CONFLICT", message="印章移交冲突")
        return self._seal_dict(row, detail=True)

    def accept_seal_transfer(self, seal_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("seal:custody")
        row = self.repo.get_seal(seal_id, for_update=True)
        if row is None:
            raise AppError("印章不存在", code="SEAL_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        event = self.repo.pending_transfer(seal_id)
        if event is None or row.status != "TRANSFER_PENDING":
            raise AppError("待接收移交不存在", code="SEAL_TRANSFER_NOT_FOUND", status_code=404)
        if int(event.to_custodian_user_id or 0) != int(self.ctx.user_id):
            raise AppError("仅目标保管人可接收", code="SEAL_CUSTODY_DENIED", status_code=403)
        event.status = "COMPLETED"
        self.repo.save(event)
        previous = int(row.custodian_user_id)
        row.custodian_user_id = int(event.to_custodian_user_id)
        row.status = transition_seal(row.status, "ACTIVE")
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.repo.create_custody_event(
            park_id=row.park_id,
            seal_id=row.id,
            event_type="TRANSFER_ACCEPTED",
            status="COMPLETED",
            from_custodian_user_id=previous,
            to_custodian_user_id=row.custodian_user_id,
            actor_user_id=self.ctx.user_id,
            reason=bounded_text(data["reason"], field="reason", maximum=1000, required=True),
            occurred_at=utc_now(),
        )
        self.work_items.complete_by_source(
            source_type="SEAL_TRANSFER",
            source_id=str(event.id),
            item_type="SEAL_TRANSFER_ACCEPT",
            commit=False,
        )
        self.audit.record(
            action="transfer_accept",
            resource_type="SEAL_ASSET",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"from": previous, "to": row.custodian_user_id},
        )
        self._commit(code="SEAL_TRANSFER_CONFLICT", message="印章接收冲突")
        return self._seal_dict(row, detail=True)

    def transition_seal_state(
        self, seal_id: int, target: str, event_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        self._permission("seal:manage")
        row = self.repo.get_seal(seal_id, for_update=True)
        if row is None:
            raise AppError("印章不存在", code="SEAL_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        pending = self.repo.pending_transfer(seal_id)
        if pending is not None:
            pending.status = "CANCELLED"
            self.repo.save(pending)
            self.work_items.cancel_by_source(
                source_type="SEAL_TRANSFER",
                source_id=str(pending.id),
                item_type="SEAL_TRANSFER_ACCEPT",
                commit=False,
            )
        row.status = transition_seal(row.status, target)
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.repo.create_custody_event(
            park_id=row.park_id,
            seal_id=row.id,
            event_type=event_type,
            status="COMPLETED",
            from_custodian_user_id=row.custodian_user_id,
            to_custodian_user_id=row.custodian_user_id,
            actor_user_id=self.ctx.user_id or None,
            reason=bounded_text(data["reason"], field="reason", maximum=1000, required=True),
            occurred_at=utc_now(),
        )
        self.audit.record(
            action=event_type.lower(),
            resource_type="SEAL_ASSET",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"status": row.status, "reason": data["reason"]},
        )
        self._commit(code="SEAL_STATE_CONFLICT", message="印章状态更新冲突")
        return self._seal_dict(row, detail=True)

    @staticmethod
    def _seal_application_dict(row, approval=None, receipt=None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "park_id": row.park_id,
            "seal_id": int(row.seal_id),
            "record_id": int(row.record_id),
            "revision_id": int(row.revision_id),
            "revision_checksum": row.revision_checksum,
            "purpose": row.purpose,
            "copy_count": int(row.copy_count),
            "requested_for": row.requested_for.isoformat(),
            "applicant_user_id": int(row.applicant_user_id),
            "approval_id": row.approval_id,
            "approval_status": approval.status if approval else None,
            "status": row.status,
            "lock_version": int(row.lock_version),
            "receipt": (
                {
                    "id": int(receipt.id),
                    "revision_checksum": receipt.revision_checksum,
                    "copy_count": int(receipt.copy_count),
                    "executor_user_id": int(receipt.executor_user_id),
                    "evidence_attachment_id": receipt.evidence_attachment_id,
                    "executed_at": receipt.executed_at.isoformat(),
                }
                if receipt
                else None
            ),
        }

    def create_seal_application(
        self, data: dict[str, Any], *, application_key: str
    ) -> dict[str, Any]:
        self._permission("seal:apply")
        previous = self.repo.seal_application_by_key(application_key)
        if previous is not None:
            return self._seal_application_dict(
                previous,
                self.repo.approval(previous.approval_id),
                self.repo.get_seal_receipt(previous.id),
            )
        seal = self.repo.get_seal(int(data["seal_id"]))
        if seal is None or seal.status != "ACTIVE":
            raise AppError("印章不可用", code="SEAL_UNAVAILABLE", status_code=409)
        record = self._require_record(int(data["record_id"]))
        revision = self._require_revision(int(data["revision_id"]))
        if int(revision.record_id) != int(record.id):
            raise AppError(
                "档案版本不属于指定档案", code="RECORD_REVISION_MISMATCH", status_code=409
            )
        if seal.park_id != record.park_id:
            raise AppError(
                "印章与档案园区不匹配", code="SEAL_RECORD_PARK_MISMATCH", status_code=409
            )
        latest = self.repo.latest_revision(record.id)
        if latest is None or int(latest.id) != int(revision.id):
            raise AppError(
                "用印必须绑定档案最新版本", code="RECORD_REVISION_STALE", status_code=409
            )
        requested_for = _naive_utc(data["requested_for"], field="requested_for")
        row = self.repo.create_seal_application(
            park_id=record.park_id,
            seal_id=int(seal.id),
            record_id=int(record.id),
            revision_id=int(revision.id),
            revision_checksum=revision.checksum_sha256,
            purpose=bounded_text(data["purpose"], field="purpose", maximum=1000, required=True),
            copy_count=int(data["copy_count"]),
            requested_for=requested_for,
            applicant_user_id=self.ctx.user_id,
            status="PENDING_APPROVAL",
            application_key=application_key,
            lock_version=1,
        )
        self._create_approval(
            row=row,
            biz_type="SEAL_USE",
            definition_code=data["definition_code"],
            request_key=application_key,
            title=f"用印申请：{seal.name} / {record.record_no}",
            park_id=record.park_id,
            snapshot={
                "seal_id": seal.id,
                "record_id": record.id,
                "revision_id": revision.id,
                "revision_checksum": revision.checksum_sha256,
                "copy_count": row.copy_count,
            },
        )
        self.audit.record(
            action="apply",
            resource_type="SEAL_USE_APPLICATION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={"seal_id": seal.id, "record_id": record.id, "revision_id": revision.id},
        )
        self.session.commit()
        return self._seal_application_dict(row, self.repo.approval(row.approval_id), None)

    def list_seal_applications(self, *, status: str | None) -> list[dict[str, Any]]:
        self._permission("seal:read", "seal:apply")
        return [
            self._seal_application_dict(
                row,
                self.repo.approval(row.approval_id),
                self.repo.get_seal_receipt(row.id),
            )
            for row in self.repo.list_seal_applications(status=status)
        ]

    def refresh_seal_application(self, application_id: int) -> dict[str, Any]:
        self._permission("seal:read", "seal:apply")
        row = self.repo.get_seal_application(application_id, for_update=True)
        if row is None:
            raise AppError("用印申请不存在", code="SEAL_USE_NOT_FOUND", status_code=404)
        approval = self.repo.approval(row.approval_id)
        if row.status in {"PENDING_APPROVAL", "APPROVAL_RETURNED"}:
            row.status = self._approval_state(approval)
            row.lock_version = int(row.lock_version) + 1
            self.repo.save(row)
            self.session.commit()
        return self._seal_application_dict(row, approval, self.repo.get_seal_receipt(row.id))

    def execute_seal_application(
        self, application_id: int, data: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        self._permission("seal:execute")
        fingerprint = canonical_payload_hash(
            {
                "application_id": int(application_id),
                "expected_version": int(data["expected_version"]),
                "evidence_attachment_id": data.get("evidence_attachment_id"),
                "emergency_override_reason": data.get("emergency_override_reason"),
            }
        )
        previous = self.repo.seal_receipt_by_key(idempotency_key)
        if previous is not None:
            if (
                int(previous.application_id) != int(application_id)
                or previous.command_fingerprint != fingerprint
            ):
                raise AppError("幂等键请求内容不一致", code="IDEMPOTENCY_CONFLICT", status_code=409)
            row = self.repo.get_seal_application(application_id)
            if row is None:
                raise AppError("用印申请不存在", code="SEAL_USE_NOT_FOUND", status_code=404)
            return self._seal_application_dict(row, self.repo.approval(row.approval_id), previous)
        row = self.repo.get_seal_application(application_id, for_update=True)
        if row is None:
            raise AppError("用印申请不存在", code="SEAL_USE_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        approval = self.repo.approval(row.approval_id)
        row.status = self._approval_state(approval)
        if row.status != "APPROVED":
            raise AppError("用印审批未通过", code="APPROVAL_NOT_APPROVED", status_code=409)
        seal = self.repo.get_seal(int(row.seal_id), for_update=True)
        if seal is None or seal.status != "ACTIVE":
            raise AppError("印章不可用", code="SEAL_UNAVAILABLE", status_code=409)
        if int(seal.custodian_user_id) != int(self.ctx.user_id):
            raise AppError("仅印章保管人可执行用印", code="SEAL_CUSTODY_DENIED", status_code=403)
        high_risk = seal.kind in {
            "OFFICIAL",
            "CONTRACT",
            "FINANCE",
            "LEGAL_REPRESENTATIVE",
            "ELECTRONIC",
        }
        participants = {
            int(row.applicant_user_id),
            int(approval.approver_user_id or 0),
            int(self.ctx.user_id),
        }
        override_reason = bounded_text(
            data.get("emergency_override_reason"),
            field="emergency_override_reason",
            maximum=1000,
        )
        separation_violated = high_risk and (0 in participants or len(participants) != 3)
        if separation_violated and not (
            override_reason and self.ctx.has_permission("seal:execute_override")
        ):
            raise AppError(
                "高风险用印要求申请人、最终审批人和执行人相互独立",
                code="SEAL_USE_SEPARATION_OF_DUTIES",
                status_code=403,
            )
        latest = self.repo.latest_revision(int(row.record_id))
        if (
            latest is None
            or int(latest.id) != int(row.revision_id)
            or latest.checksum_sha256 != row.revision_checksum
        ):
            raise AppError(
                "档案版本已变化，禁止用印", code="RECORD_REVISION_STALE", status_code=409
            )
        evidence_id = (
            int(data["evidence_attachment_id"]) if data.get("evidence_attachment_id") else None
        )
        if evidence_id is not None and self.repo.get_attachment(evidence_id) is None:
            raise AppError("用印证据附件不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
        receipt = self.repo.create_seal_receipt(
            park_id=row.park_id,
            application_id=int(row.id),
            revision_checksum=row.revision_checksum,
            copy_count=int(row.copy_count),
            executor_user_id=self.ctx.user_id,
            evidence_attachment_id=evidence_id,
            idempotency_key=idempotency_key,
            command_fingerprint=fingerprint,
            executed_at=utc_now(),
        )
        row.status = "EXECUTED"
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        self.audit.record(
            action="execute",
            resource_type="SEAL_USE_APPLICATION",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "seal_id": row.seal_id,
                "record_id": row.record_id,
                "revision_checksum": row.revision_checksum,
                "copy_count": row.copy_count,
                "separation_override": separation_violated,
                "override_reason": override_reason or None,
            },
        )
        self._commit(code="SEAL_USE_CONFLICT", message="用印执行并发冲突")
        return self._seal_application_dict(row, self.repo.approval(row.approval_id), receipt)

    # Truthful signature providers and envelopes
    @staticmethod
    def _provider_dict(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return {
            "id": int(row.id),
            "code": row.code,
            "name": row.name,
            "adapter_kind": row.adapter_kind,
            "status": row.status,
            "credential_ref_configured": bool(row.credential_ref),
            "health": dict(row.health_json or {}),
            "live_verified": bool(row.live_verified),
            "lock_version": int(row.lock_version),
        }

    def list_signature_providers(self) -> list[dict[str, Any]]:
        self._permission("signature:read")
        return [self._provider_dict(row) for row in self.repo.list_signature_providers()]

    def create_signature_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("signature:manage")
        self._tenant_level()
        adapter = signature_adapter(data["adapter_kind"])
        # An API declaration can never prove a live external connection. External providers
        # remain NOT_CONNECTED until a separately implemented credential/health adapter verifies them.
        status = "SANDBOX" if adapter == "LOCAL_SANDBOX" else "NOT_CONNECTED"
        row = self.repo.create_signature_provider(
            code=bounded_text(data["code"], field="code", maximum=32, required=True).upper(),
            name=bounded_text(data["name"], field="name", maximum=128, required=True),
            adapter_kind=adapter,
            status=status,
            credential_ref=(
                bounded_text(data.get("credential_ref"), field="credential_ref", maximum=128)
                or None
            ),
            health_json={
                "mode": "LOCAL_NON_LEGAL_SIMULATION"
                if adapter == "LOCAL_SANDBOX"
                else "UNVERIFIED",
                "checked_at": utc_now().isoformat(),
            },
            live_verified=False,
            lock_version=1,
        )
        self.audit.record(
            action="create",
            resource_type="SIGNATURE_PROVIDER",
            resource_id=row.id,
            detail={"code": row.code, "status": row.status, "live_verified": False},
        )
        self._commit(code="SIGNATURE_PROVIDER_CONFLICT", message="签章服务编码冲突")
        return self._provider_dict(row)

    def _envelope_dict(self, row, *, detail: bool = False) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        result = {
            "id": int(row.id),
            "park_id": row.park_id,
            "provider_id": int(row.provider_id),
            "record_id": int(row.record_id),
            "revision_id": int(row.revision_id),
            "revision_checksum": row.revision_checksum,
            "envelope_no": row.envelope_no,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "purpose": row.purpose,
            "status": row.status,
            "provider_ref": row.provider_ref,
            "live_verified": bool(row.live_verified),
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "lock_version": int(row.lock_version),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        if detail:
            result["participants"] = [
                {
                    "id": int(item.id),
                    "position": int(item.position),
                    "role": item.role,
                    "display_name": item.display_name,
                    "contact_masked": item.contact_masked,
                    "status": item.status,
                    "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                }
                for item in self.repo.signature_participants(row.id)
            ]
            result["events"] = [
                {
                    "id": int(item.id),
                    "source_event_id": item.source_event_id,
                    "event_type": item.event_type,
                    "payload_hash": item.payload_hash,
                    "detail": item.detail_json,
                    "occurred_at": item.occurred_at.isoformat(),
                    "received_at": item.received_at.isoformat(),
                }
                for item in self.repo.signature_events(row.id)
            ]
        return result

    def list_signature_envelopes(self, *, status: str | None) -> list[dict[str, Any]]:
        self._permission("signature:read")
        return [
            self._envelope_dict(row) for row in self.repo.list_signature_envelopes(status=status)
        ]

    def get_signature_envelope(self, envelope_id: int) -> dict[str, Any]:
        self._permission("signature:read")
        row = self.repo.get_signature_envelope(envelope_id)
        if row is None:
            raise AppError("签署信封不存在", code="SIGNATURE_ENVELOPE_NOT_FOUND", status_code=404)
        return self._envelope_dict(row, detail=True)

    def create_signature_envelope(self, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("signature:write")
        provider = self.repo.get_signature_provider(int(data["provider_id"]))
        if provider is None:
            raise AppError("签章服务不存在", code="SIGNATURE_PROVIDER_NOT_FOUND", status_code=404)
        if provider.status not in {"SANDBOX", "CONNECTED"}:
            raise AppError("签章服务未连接", code="SIGNATURE_PROVIDER_UNAVAILABLE", status_code=409)
        record = self._require_record(int(data["record_id"]))
        revision = self._require_revision(int(data["revision_id"]))
        latest = self.repo.latest_revision(record.id)
        if (
            int(revision.record_id) != int(record.id)
            or latest is None
            or int(latest.id) != int(revision.id)
        ):
            raise AppError(
                "签署必须绑定档案最新版本", code="RECORD_REVISION_STALE", status_code=409
            )
        participants = list(data["participants"])
        sequence = next_number(
            self.session,
            tenant_id=self.ctx.tenant_id,
            biz_type="SIGNATURE_ENVELOPE",
            period_key=utc_now().strftime("%Y%m"),
        )
        row = self.repo.create_signature_envelope(
            park_id=record.park_id,
            provider_id=int(provider.id),
            record_id=int(record.id),
            revision_id=int(revision.id),
            revision_checksum=revision.checksum_sha256,
            envelope_no=f"SIG-{utc_now():%Y%m}-{sequence:06d}",
            source_type=bounded_text(
                data["source_type"], field="source_type", maximum=64, required=True
            ).upper(),
            source_id=bounded_text(data["source_id"], field="source_id", maximum=64, required=True),
            purpose=bounded_text(data["purpose"], field="purpose", maximum=500, required=True),
            status="DRAFT",
            live_verified=False,
            lock_version=1,
            created_by=self.ctx.user_id or None,
        )
        for position, participant in enumerate(participants, start=1):
            self.repo.create_signature_participant(
                envelope_id=int(row.id),
                position=position,
                role=signature_role(participant["role"]),
                display_name=bounded_text(
                    participant["display_name"],
                    field="display_name",
                    maximum=128,
                    required=True,
                ),
                contact_masked=(
                    bounded_text(
                        participant.get("contact_masked"), field="contact_masked", maximum=128
                    )
                    or None
                ),
                status="PENDING",
            )
        self.audit.record(
            action="create",
            resource_type="SIGNATURE_ENVELOPE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "envelope_no": row.envelope_no,
                "revision_checksum": row.revision_checksum,
                "provider_status": provider.status,
            },
        )
        self._commit(code="SIGNATURE_ENVELOPE_CONFLICT", message="签署信封来源或编号冲突")
        return self._envelope_dict(row, detail=True)

    def dispatch_signature_envelope(self, envelope_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._permission("signature:dispatch")
        row = self.repo.get_signature_envelope(envelope_id, for_update=True)
        if row is None:
            raise AppError("签署信封不存在", code="SIGNATURE_ENVELOPE_NOT_FOUND", status_code=404)
        _expected(row, data["expected_version"])
        if row.status != "DRAFT":
            raise AppError(
                "签署信封状态不可发送", code="SIGNATURE_ENVELOPE_STATE_INVALID", status_code=409
            )
        latest = self.repo.latest_revision(int(row.record_id))
        if (
            latest is None
            or int(latest.id) != int(row.revision_id)
            or latest.checksum_sha256 != row.revision_checksum
        ):
            raise AppError(
                "档案版本已变化，禁止发送", code="RECORD_REVISION_STALE", status_code=409
            )
        provider = self.repo.get_signature_provider(int(row.provider_id), for_update=True)
        if provider is None:
            raise AppError("签章服务不存在", code="SIGNATURE_PROVIDER_NOT_FOUND", status_code=404)
        if provider.adapter_kind != "LOCAL_SANDBOX" or provider.status != "SANDBOX":
            # No external adapter is installed in this vertical. Never fabricate success.
            raise AppError(
                "外部签章适配器或有效凭据尚未完成验证",
                code="SIGNATURE_EXTERNAL_ADAPTER_UNAVAILABLE",
                status_code=503,
            )
        now = utc_now()
        row.status = "SANDBOX_COMPLETED"
        row.provider_ref = f"sandbox:{uuid.uuid4().hex}"
        row.live_verified = False
        row.completed_at = now
        row.lock_version = int(row.lock_version) + 1
        self.repo.save(row)
        for participant in self.repo.signature_participants(row.id):
            participant.status = "COMPLETED"
            participant.completed_at = now
            self.repo.save(participant)
        payload = {
            "envelope_no": row.envelope_no,
            "status": "SANDBOX_COMPLETED",
            "revision_checksum": row.revision_checksum,
            "legal_effect": False,
        }
        self.repo.create_signature_event(
            provider_id=int(provider.id),
            envelope_id=int(row.id),
            source_event_id=f"sandbox-{uuid.uuid4().hex}",
            event_type="SANDBOX_COMPLETED",
            payload_hash=canonical_payload_hash(payload),
            detail_json=payload,
            occurred_at=now,
            received_at=now,
        )
        self.audit.record(
            action="sandbox_dispatch",
            resource_type="SIGNATURE_ENVELOPE",
            resource_id=row.id,
            park_id=row.park_id,
            detail={
                "status": row.status,
                "live_verified": False,
                "legal_effect": False,
                "reason": data["reason"],
            },
        )
        self._commit(code="SIGNATURE_ENVELOPE_CONFLICT", message="签署信封发送冲突")
        return self._envelope_dict(row, detail=True)
