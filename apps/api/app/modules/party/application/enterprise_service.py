"""Application use-cases for governed enterprise profiles."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.party.application.party_service import PartyService
from app.modules.party.domain.enterprise_rules import (
    CREDENTIAL_STATUSES,
    CREDENTIAL_TYPES,
    EMPLOYEE_SIZE_BANDS,
    LOCAL_CREDENTIAL_REVIEWS,
    REGISTRATION_STATUSES,
    RISK_CATEGORIES,
    RISK_RESOLUTION_TYPES,
    RISK_SEVERITIES,
    SOURCE_TYPES,
    TAG_TYPES,
    canonical_relationship,
    capital_value,
    confidence_value,
    currency_value,
    effective_credential_status,
    enterprise_completeness,
    enterprise_risk_summary,
    enum_value,
    normalize_tag_name,
    optional_text,
    ownership_value,
    reduce_organization_identifier,
    required_text,
    website_value,
)
from app.modules.party.infrastructure.enterprise_repository import PartyEnterpriseRepository
from app.shared.tenant_context import TenantContext

T = TypeVar("T")


class PartyEnterpriseService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.party = PartyService(session, ctx)
        self.repo = PartyEnterpriseRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _organization(self, party_id: int, *, write: bool = False):
        row = self.party._require_visible(party_id)
        if row.party_type != "ORGANIZATION":
            raise AppError(
                "仅组织主体支持企业画像",
                code="ENTERPRISE_PROFILE_ORGANIZATION_REQUIRED",
                status_code=400,
            )
        if write:
            self.party._assert_can_write_party(row)
        return row

    def _park_id(self, party_id: int) -> int | None:
        visible = sorted(
            park_id
            for park_id in self.repo.party_active_park_ids(party_id)
            if self.ctx.allows_park(park_id)
        )
        return visible[0] if visible else None

    def _event(
        self,
        *,
        party_id: int,
        event_type: str,
        source_type: str,
        source_id: int,
        payload: dict[str, Any],
        generation: int,
    ) -> None:
        self.repo.add_event(
            event_type=event_type,
            source_type=source_type,
            source_id=str(source_id),
            park_id=self._park_id(party_id),
            payload={"party_id": party_id, **payload},
            idempotency_key=(
                f"party-enterprise:{event_type}:{self.ctx.tenant_id}:{source_type}:{source_id}:v{generation}"
            ),
        )

    def _commit_or_conflict(self, code: str, message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    def _insert_or_conflict(self, operation: Callable[[], T], *, code: str, message: str) -> T:
        """Map uniqueness/FK races raised by repository flush into a stable API conflict."""

        try:
            return operation()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(message, code=code, status_code=409) from exc

    @staticmethod
    def _decimal(value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None

    def _profile_dict(self, party, profile) -> dict[str, Any]:
        dimensions = self.repo.completeness_dimensions(party, profile)
        completeness = enterprise_completeness(dimensions)
        return {
            "party_id": party.id,
            "party_name": party.name,
            "credit_code": party.credit_code,
            "profile_id": profile.id if profile else None,
            "short_name": profile.short_name if profile else None,
            "legal_representative": profile.legal_representative if profile else None,
            "established_on": profile.established_on.isoformat()
            if profile and profile.established_on
            else None,
            "registered_capital": self._decimal(profile.registered_capital) if profile else None,
            "capital_currency": profile.capital_currency if profile else None,
            "registration_status": profile.registration_status if profile else "UNKNOWN",
            "registration_authority": profile.registration_authority if profile else None,
            "industry_code": profile.industry_code if profile else None,
            "industry_name": profile.industry_name if profile else None,
            "employee_size_band": profile.employee_size_band if profile else "UNKNOWN",
            "website": profile.website if profile else None,
            "business_scope": profile.business_scope if profile else None,
            "provider_status": profile.provider_status if profile else "NOT_CONNECTED",
            "last_verified_at": (
                profile.last_verified_at.isoformat()
                if profile and profile.last_verified_at
                else None
            ),
            "lock_version": profile.lock_version if profile else 0,
            "completeness_score": completeness.score,
            "missing_dimensions": list(completeness.missing),
        }

    def get_profile(self, party_id: int) -> dict[str, Any]:
        party = self._organization(party_id)
        return self._profile_dict(party, self.repo.profile(party_id))

    def _profile_values(self, data: dict[str, Any], *, existing=None) -> dict[str, Any]:
        values: dict[str, Any] = {}
        text_fields = {
            "short_name": 128,
            "legal_representative": 128,
            "registration_authority": 255,
            "industry_code": 32,
            "industry_name": 128,
            "business_scope": 4000,
        }
        for field, limit in text_fields.items():
            if field in data:
                values[field] = optional_text(data.get(field), field, max_length=limit)
        if "website" in data:
            values["website"] = website_value(data.get("website"))
        if "established_on" in data:
            established = data.get("established_on")
            if established is not None and established > utc_now().date():
                raise AppError("成立日期不能晚于今天", code="VALIDATION_ERROR", status_code=400)
            values["established_on"] = established
        if "registered_capital" in data:
            values["registered_capital"] = capital_value(data.get("registered_capital"))
        if "capital_currency" in data:
            capital = values.get(
                "registered_capital",
                existing.registered_capital if existing is not None else None,
            )
            values["capital_currency"] = currency_value(
                data.get("capital_currency"), required=capital is not None
            )
        final_capital = values.get(
            "registered_capital", existing.registered_capital if existing is not None else None
        )
        final_currency = values.get(
            "capital_currency", existing.capital_currency if existing is not None else None
        )
        if final_capital is not None and final_currency is None:
            raise AppError("注册资本存在时币种必填", code="VALIDATION_ERROR", status_code=400)
        if final_capital is None and "registered_capital" in values:
            values["capital_currency"] = None
        if "registration_status" in data:
            values["registration_status"] = enum_value(
                data.get("registration_status"), REGISTRATION_STATUSES, "registration_status"
            )
        if "employee_size_band" in data:
            values["employee_size_band"] = enum_value(
                data.get("employee_size_band"), EMPLOYEE_SIZE_BANDS, "employee_size_band"
            )
        return values

    def save_profile(self, party_id: int, data: dict[str, Any]) -> dict[str, Any]:
        party = self._organization(party_id, write=True)
        profile = self.repo.profile(party_id, for_update=True)
        expected = data.pop("expected_lock_version", None)
        if profile is None:
            if expected not in {None, 0}:
                raise AppError(
                    "企业画像版本冲突", code="ENTERPRISE_PROFILE_CONFLICT", status_code=409
                )
            values = self._profile_values(data)
            profile = self._insert_or_conflict(
                lambda: self.repo.add_profile(
                    party_id=party_id,
                    values={
                        **values,
                        "provider_status": "NOT_CONNECTED",
                        "lock_version": 1,
                        "created_by": self.ctx.user_id or None,
                        "updated_by": self.ctx.user_id or None,
                    },
                ),
                code="ENTERPRISE_PROFILE_CONFLICT",
                message="企业画像版本或唯一约束冲突",
            )
            action = "create"
        else:
            if expected is None or int(expected) != int(profile.lock_version):
                raise AppError(
                    "企业画像版本冲突", code="ENTERPRISE_PROFILE_CONFLICT", status_code=409
                )
            values = self._profile_values(data, existing=profile)
            for field, value in values.items():
                setattr(profile, field, value)
            profile.provider_status = "NOT_CONNECTED"
            profile.last_verified_at = None
            profile.updated_by = self.ctx.user_id or None
            profile.lock_version += 1
            self.session.add(profile)
            self.session.flush()
            action = "update"
        self.audit.record(
            action=action,
            resource_type="PARTY_ENTERPRISE_PROFILE",
            resource_id=profile.id,
            park_id=self._park_id(party_id),
            detail={"party_id": party_id, "fields": sorted(data)},
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_PROFILE_CHANGED",
            source_type="PARTY_ENTERPRISE_PROFILE",
            source_id=profile.id,
            payload={"action": action, "lock_version": profile.lock_version},
            generation=profile.lock_version,
        )
        self._commit_or_conflict("ENTERPRISE_PROFILE_CONFLICT", "企业画像版本或唯一约束冲突")
        return self._profile_dict(party, profile)

    def directory(
        self,
        *,
        page: int,
        page_size: int,
        keyword: str | None,
        status: str | None,
        blacklist_status: str | None,
        registration_status: str | None,
        industry: str | None,
        min_completeness: int | None,
        max_completeness: int | None,
        local_risk_level: str | None,
        sort_by: str,
        sort_order: str,
    ) -> dict[str, Any]:
        if local_risk_level is not None and not self.ctx.has_permission("party:risk_read"):
            raise AppError("无风险筛选权限", code="PERMISSION_DENIED", status_code=403)
        normalized_risk = None
        if local_risk_level is not None:
            normalized_risk = str(local_risk_level).upper()
            if normalized_risk not in RISK_SEVERITIES | {"NONE"}:
                raise AppError("本地风险等级非法", code="VALIDATION_ERROR", status_code=400)
        normalized_registration = None
        if registration_status:
            normalized_registration = enum_value(
                registration_status, REGISTRATION_STATUSES, "registration_status"
            )
        if status and status not in {"ACTIVE", "INACTIVE"}:
            raise AppError("Party 状态非法", code="VALIDATION_ERROR", status_code=400)
        if blacklist_status and blacklist_status not in {"NORMAL", "BLACKLISTED"}:
            raise AppError("黑名单状态非法", code="VALIDATION_ERROR", status_code=400)
        page = max(int(page), 1)
        page_size = min(max(int(page_size), 1), 100)
        minimum = None if min_completeness is None else max(0, min(100, int(min_completeness)))
        maximum = None if max_completeness is None else max(0, min(100, int(max_completeness)))
        if minimum is not None and maximum is not None and minimum > maximum:
            raise AppError("完整度区间非法", code="VALIDATION_ERROR", status_code=400)
        if sort_by not in {"name", "updated_at", "completeness"} or sort_order not in {
            "asc",
            "desc",
        }:
            raise AppError("排序字段非法", code="VALIDATION_ERROR", status_code=400)
        total, rows = self.repo.directory(
            offset=(page - 1) * page_size,
            limit=page_size,
            keyword=keyword,
            status=status,
            blacklist_status=blacklist_status,
            registration_status=normalized_registration,
            industry=industry,
            min_completeness=minimum,
            max_completeness=maximum,
            local_risk_level=normalized_risk,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        items = []
        for party, profile, score in rows:
            item = {
                "party_id": party.id,
                "name": party.name,
                "short_name": profile.short_name if profile else None,
                "credit_code": party.credit_code,
                "status": party.status,
                "blacklist_status": party.risk_status,
                "registration_status": profile.registration_status if profile else "UNKNOWN",
                "industry_code": profile.industry_code if profile else None,
                "industry_name": profile.industry_name if profile else None,
                "employee_size_band": profile.employee_size_band if profile else "UNKNOWN",
                "provider_status": profile.provider_status if profile else "NOT_CONNECTED",
                "completeness_score": score,
                "park_ids": sorted(self.repo.party_active_park_ids(party.id)),
            }
            if self.ctx.has_permission("party:risk_read"):
                item["local_risk"] = self._risk_summary(party.id)
            items.append(item)
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def _validate_evidence_attachment(self, party_id: int, attachment_id: int):
        attachment = self.repo.attachment(attachment_id)
        if attachment is None:
            raise AppError("附件不存在", code="ATTACHMENT_NOT_FOUND", status_code=404)
        active_parks = self.repo.party_active_park_ids(party_id)
        if not active_parks:
            if attachment.park_id is not None:
                raise AppError(
                    "附件园区与未关联主体不兼容", code="PARK_SCOPE_DENIED", status_code=403
                )
        elif (
            attachment.park_id is None
            or attachment.park_id not in active_parks
            or not self.ctx.allows_park(attachment.park_id)
        ):
            raise AppError("附件园区与主体范围不兼容", code="PARK_SCOPE_DENIED", status_code=403)
        return attachment

    @staticmethod
    def _relationship_dict(row, source, target) -> dict[str, Any]:
        return {
            "id": row.id,
            "source_party_id": row.source_party_id,
            "source_party_name": source.name,
            "target_party_id": row.target_party_id,
            "target_party_name": target.name,
            "relationship_type": row.relationship_type,
            "ownership_percent": (
                format(row.ownership_percent, "f") if row.ownership_percent is not None else None
            ),
            "source_type": row.source_type,
            "source_reference": row.source_reference,
            "attachment_id": row.attachment_id,
            "started_on": row.started_on.isoformat() if row.started_on else None,
            "status": row.status,
            "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            "end_reason": row.end_reason,
            "lock_version": row.lock_version,
        }

    def list_relationships(self, party_id: int, *, include_ended: bool) -> list[dict[str, Any]]:
        self._organization(party_id)
        result = []
        for row in self.repo.relationships(party_id, include_ended=include_ended):
            source = self.repo.parties.get_by_id(row.source_party_id)
            target = self.repo.parties.get_by_id(row.target_party_id)
            if source is None or target is None:
                continue
            result.append(self._relationship_dict(row, source, target))
        return result

    def create_relationship(self, party_id: int, data: dict[str, Any]) -> dict[str, Any]:
        path_party = self._organization(party_id, write=True)
        target = self._organization(int(data["target_party_id"]))
        source_id, target_id, kind = canonical_relationship(
            party_id, target.id, data.get("relationship_type")
        )
        source = path_party if source_id == path_party.id else target
        canonical_target = target if target_id == target.id else path_party
        source_type = enum_value(
            data.get("source_type"), SOURCE_TYPES, "source_type", default="MANUAL"
        )
        if source_type != "MANUAL":
            raise AppError(
                "外部企业关系提供商未连接", code="PROVIDER_NOT_CONNECTED", status_code=503
            )
        ownership = ownership_value(data.get("ownership_percent"), kind)
        attachment_id = data.get("attachment_id")
        if attachment_id is not None:
            self._validate_evidence_attachment(party_id, int(attachment_id))
        self.repo.lock_relationship_graph()
        existing = self.repo.active_relationship(
            source_party_id=source_id,
            target_party_id=target_id,
            relationship_type=kind,
        )
        if existing is not None:
            return self._relationship_dict(existing, source, canonical_target)
        if kind == "PARENT_OF" and self.repo.parent_cycle_exists(
            source_party_id=source_id, target_party_id=target_id
        ):
            raise AppError(
                "父子企业关系会形成闭环",
                code="ENTERPRISE_RELATIONSHIP_CYCLE",
                status_code=409,
            )
        row = self._insert_or_conflict(
            lambda: self.repo.add_relationship(
                {
                    "source_party_id": source_id,
                    "target_party_id": target_id,
                    "relationship_type": kind,
                    "ownership_percent": ownership,
                    "source_type": source_type,
                    "source_reference": optional_text(
                        data.get("source_reference"), "source_reference", max_length=128
                    ),
                    "attachment_id": int(attachment_id) if attachment_id is not None else None,
                    "started_on": data.get("started_on"),
                    "status": "ACTIVE",
                    "lock_version": 1,
                    "created_by": self.ctx.user_id or None,
                }
            ),
            code="ENTERPRISE_RELATIONSHIP_CONFLICT",
            message="企业关系已存在或并发冲突",
        )
        self.audit.record(
            action="create",
            resource_type="PARTY_ENTERPRISE_RELATIONSHIP",
            resource_id=row.id,
            park_id=self._park_id(party_id),
            detail={
                "source_party_id": source_id,
                "target_party_id": target_id,
                "relationship_type": kind,
                "attachment_id": attachment_id,
            },
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_RELATIONSHIP_CREATED",
            source_type="PARTY_ENTERPRISE_RELATIONSHIP",
            source_id=row.id,
            payload={"relationship_type": kind, "target_party_id": target.id},
            generation=1,
        )
        self._commit_or_conflict("ENTERPRISE_RELATIONSHIP_CONFLICT", "企业关系已存在或并发冲突")
        return self._relationship_dict(row, source, canonical_target)

    def end_relationship(
        self, party_id: int, relationship_id: int, *, expected_lock_version: int, reason: str
    ) -> dict[str, Any]:
        self._organization(party_id, write=True)
        row = self.repo.relationship(relationship_id, party_id, for_update=True)
        if row is None:
            raise AppError(
                "企业关系不存在", code="ENTERPRISE_RELATIONSHIP_NOT_FOUND", status_code=404
            )
        source = self._organization(row.source_party_id)
        target = self._organization(row.target_party_id)
        if row.status != "ACTIVE" or row.lock_version != int(expected_lock_version):
            raise AppError(
                "企业关系版本冲突", code="ENTERPRISE_RELATIONSHIP_CONFLICT", status_code=409
            )
        row.status = "ENDED"
        row.ended_at = utc_now()
        row.ended_by = self.ctx.user_id or None
        row.end_reason = required_text(reason, "reason", max_length=512)
        row.lock_version += 1
        self.session.add(row)
        self.audit.record(
            action="end",
            resource_type="PARTY_ENTERPRISE_RELATIONSHIP",
            resource_id=row.id,
            park_id=self._park_id(party_id),
            detail={"party_id": party_id, "relationship_type": row.relationship_type},
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_RELATIONSHIP_ENDED",
            source_type="PARTY_ENTERPRISE_RELATIONSHIP",
            source_id=row.id,
            payload={"relationship_type": row.relationship_type},
            generation=row.lock_version,
        )
        self.session.commit()
        return self._relationship_dict(row, source, target)

    def _require_credential(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无企业证照权限", code="PERMISSION_DENIED", status_code=403)

    @staticmethod
    def _credential_dict(row) -> dict[str, Any]:
        effective = effective_credential_status(row.status, row.expires_on, today=utc_now().date())
        return {
            "id": row.id,
            "party_id": row.party_id,
            "attachment_id": row.attachment_id,
            "credential_type": row.credential_type,
            "identifier_masked": row.identifier_masked,
            "issuer": row.issuer,
            "issued_on": row.issued_on.isoformat() if row.issued_on else None,
            "expires_on": row.expires_on.isoformat() if row.expires_on else None,
            "status": row.status,
            "effective_status": effective,
            "verification_status": row.verification_status,
            "review_reason": row.review_reason,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "lock_version": row.lock_version,
        }

    def list_credentials(self, party_id: int, *, include_archived: bool) -> list[dict[str, Any]]:
        self._require_credential("party:credential_read")
        self._organization(party_id)
        return [
            self._credential_dict(row)
            for row in self.repo.credentials(party_id, include_archived=include_archived)
        ]

    def create_credential(self, party_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require_credential("party:credential_manage")
        self._organization(party_id, write=True)
        attachment_id = int(data["attachment_id"])
        self._validate_evidence_attachment(party_id, attachment_id)
        credential_type = enum_value(
            data.get("credential_type"), CREDENTIAL_TYPES, "credential_type"
        )
        issued_on = data.get("issued_on")
        expires_on = data.get("expires_on")
        if issued_on and expires_on and expires_on < issued_on:
            raise AppError("证照到期日早于签发日", code="VALIDATION_ERROR", status_code=400)
        fingerprint, masked = reduce_organization_identifier(data.get("identifier"))
        row = self._insert_or_conflict(
            lambda: self.repo.add_credential(
                {
                    "party_id": party_id,
                    "attachment_id": attachment_id,
                    "credential_type": credential_type,
                    "identifier_fingerprint": fingerprint,
                    "identifier_masked": masked,
                    "issuer": optional_text(data.get("issuer"), "issuer", max_length=255),
                    "issued_on": issued_on,
                    "expires_on": expires_on,
                    "status": "ACTIVE",
                    "verification_status": "UNVERIFIED",
                    "lock_version": 1,
                    "created_by": self.ctx.user_id or None,
                    "updated_by": self.ctx.user_id or None,
                }
            ),
            code="ENTERPRISE_CREDENTIAL_CONFLICT",
            message="企业证照已存在或并发冲突",
        )
        self.audit.record(
            action="create",
            resource_type="PARTY_ENTERPRISE_CREDENTIAL",
            resource_id=row.id,
            park_id=self._park_id(party_id),
            detail={
                "party_id": party_id,
                "credential_type": credential_type,
                "attachment_id": attachment_id,
                "identifier_masked": masked,
            },
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_CREDENTIAL_CREATED",
            source_type="PARTY_ENTERPRISE_CREDENTIAL",
            source_id=row.id,
            payload={"credential_type": credential_type},
            generation=1,
        )
        self._commit_or_conflict("ENTERPRISE_CREDENTIAL_CONFLICT", "企业证照已存在")
        return self._credential_dict(row)

    def review_credential(
        self,
        party_id: int,
        credential_id: int,
        *,
        expected_lock_version: int,
        verification_status: str,
        reason: str,
    ) -> dict[str, Any]:
        self._require_credential("party:credential_manage")
        self._organization(party_id, write=True)
        row = self.repo.credential(credential_id, party_id, for_update=True)
        if row is None:
            raise AppError(
                "企业证照不存在", code="ENTERPRISE_CREDENTIAL_NOT_FOUND", status_code=404
            )
        target = str(verification_status).strip().upper()
        if target not in LOCAL_CREDENTIAL_REVIEWS:
            raise AppError(
                "本地流程不能声明外部验真",
                code="EXTERNAL_VERIFICATION_FORBIDDEN",
                status_code=409,
            )
        if row.lock_version != int(expected_lock_version):
            raise AppError(
                "企业证照版本冲突", code="ENTERPRISE_CREDENTIAL_CONFLICT", status_code=409
            )
        row.verification_status = target
        row.review_reason = required_text(reason, "reason", max_length=512)
        row.reviewed_at = utc_now()
        row.reviewed_by = self.ctx.user_id or None
        row.updated_by = self.ctx.user_id or None
        row.lock_version += 1
        self.session.add(row)
        self.audit.record(
            action="review",
            resource_type="PARTY_ENTERPRISE_CREDENTIAL",
            resource_id=row.id,
            park_id=self._park_id(party_id),
            detail={"party_id": party_id, "verification_status": target},
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_CREDENTIAL_REVIEWED",
            source_type="PARTY_ENTERPRISE_CREDENTIAL",
            source_id=row.id,
            payload={"verification_status": target},
            generation=row.lock_version,
        )
        self.session.commit()
        return self._credential_dict(row)

    def transition_credential(
        self,
        party_id: int,
        credential_id: int,
        *,
        expected_lock_version: int,
        status: str,
        reason: str,
    ) -> dict[str, Any]:
        self._require_credential("party:credential_manage")
        self._organization(party_id, write=True)
        row = self.repo.credential(credential_id, party_id, for_update=True)
        if row is None:
            raise AppError(
                "企业证照不存在", code="ENTERPRISE_CREDENTIAL_NOT_FOUND", status_code=404
            )
        target = enum_value(status, CREDENTIAL_STATUSES, "status")
        if target == "ACTIVE":
            raise AppError("不能通过状态动作恢复证照", code="VALIDATION_ERROR", status_code=400)
        if row.lock_version != int(expected_lock_version) or row.status != "ACTIVE":
            raise AppError(
                "企业证照版本冲突", code="ENTERPRISE_CREDENTIAL_CONFLICT", status_code=409
            )
        row.status = target
        row.review_reason = required_text(reason, "reason", max_length=512)
        row.updated_by = self.ctx.user_id or None
        row.lock_version += 1
        self.session.add(row)
        self.audit.record(
            action="transition",
            resource_type="PARTY_ENTERPRISE_CREDENTIAL",
            resource_id=row.id,
            park_id=self._park_id(party_id),
            detail={"party_id": party_id, "status": target},
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_CREDENTIAL_STATUS_CHANGED",
            source_type="PARTY_ENTERPRISE_CREDENTIAL",
            source_id=row.id,
            payload={"status": target},
            generation=row.lock_version,
        )
        self.session.commit()
        return self._credential_dict(row)

    @staticmethod
    def _tag_dict(row) -> dict[str, Any]:
        return {
            "id": row.id,
            "party_id": row.party_id,
            "name": row.name,
            "tag_type": row.tag_type,
            "source_type": row.source_type,
            "source_reference": row.source_reference,
            "confidence": format(row.confidence, "f"),
            "verification_status": row.verification_status,
            "status": row.status,
            "lock_version": row.lock_version,
            "deactivated_at": row.deactivated_at.isoformat() if row.deactivated_at else None,
        }

    def list_tags(self, party_id: int, *, include_inactive: bool) -> list[dict[str, Any]]:
        self._organization(party_id)
        return [
            self._tag_dict(row)
            for row in self.repo.tags(party_id, include_inactive=include_inactive)
        ]

    def create_tag(self, party_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._organization(party_id, write=True)
        name, normalized = normalize_tag_name(data.get("name"))
        tag_type = enum_value(data.get("tag_type"), TAG_TYPES, "tag_type")
        source_type = enum_value(
            data.get("source_type"), SOURCE_TYPES, "source_type", default="MANUAL"
        )
        if source_type != "MANUAL":
            raise AppError("外部标签提供商未连接", code="PROVIDER_NOT_CONNECTED", status_code=503)
        existing = self.repo.active_tag(party_id, tag_type, normalized)
        if existing is not None:
            return self._tag_dict(existing)
        row = self._insert_or_conflict(
            lambda: self.repo.add_tag(
                {
                    "party_id": party_id,
                    "name": name,
                    "normalized_name": normalized,
                    "tag_type": tag_type,
                    "source_type": source_type,
                    "source_reference": optional_text(
                        data.get("source_reference"), "source_reference", max_length=128
                    ),
                    "confidence": confidence_value(data.get("confidence")),
                    "verification_status": "LOCALLY_REVIEWED",
                    "status": "ACTIVE",
                    "lock_version": 1,
                    "created_by": self.ctx.user_id or None,
                }
            ),
            code="ENTERPRISE_TAG_CONFLICT",
            message="企业标签已存在",
        )
        self.audit.record(
            action="create",
            resource_type="PARTY_ENTERPRISE_TAG",
            resource_id=row.id,
            park_id=self._park_id(party_id),
            detail={"party_id": party_id, "tag_type": tag_type, "name": name},
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_TAG_CREATED",
            source_type="PARTY_ENTERPRISE_TAG",
            source_id=row.id,
            payload={"tag_type": tag_type, "name": name},
            generation=1,
        )
        self._commit_or_conflict("ENTERPRISE_TAG_CONFLICT", "企业标签已存在")
        return self._tag_dict(row)

    def deactivate_tag(
        self, party_id: int, tag_id: int, *, expected_lock_version: int, reason: str
    ) -> dict[str, Any]:
        self._organization(party_id, write=True)
        row = self.repo.tag(tag_id, party_id, for_update=True)
        if row is None:
            raise AppError("企业标签不存在", code="ENTERPRISE_TAG_NOT_FOUND", status_code=404)
        if row.status != "ACTIVE" or row.lock_version != int(expected_lock_version):
            raise AppError("企业标签版本冲突", code="ENTERPRISE_TAG_CONFLICT", status_code=409)
        row.status = "INACTIVE"
        row.deactivated_at = utc_now()
        row.deactivated_by = self.ctx.user_id or None
        row.deactivation_reason = required_text(reason, "reason", max_length=512)
        row.lock_version += 1
        self.session.add(row)
        self.audit.record(
            action="deactivate",
            resource_type="PARTY_ENTERPRISE_TAG",
            resource_id=row.id,
            park_id=self._park_id(party_id),
            detail={"party_id": party_id, "tag_type": row.tag_type, "name": row.name},
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_TAG_DEACTIVATED",
            source_type="PARTY_ENTERPRISE_TAG",
            source_id=row.id,
            payload={"tag_type": row.tag_type},
            generation=row.lock_version,
        )
        self.session.commit()
        return self._tag_dict(row)

    def _require_risk(self, permission: str) -> None:
        if not self.ctx.has_permission(permission):
            raise AppError("无企业风险权限", code="PERMISSION_DENIED", status_code=403)

    @staticmethod
    def _risk_dict(signal, resolution) -> dict[str, Any]:
        return {
            "id": signal.id,
            "party_id": signal.party_id,
            "category": signal.category,
            "severity": signal.severity,
            "summary": signal.summary,
            "source_type": signal.source_type,
            "source_reference": signal.source_reference,
            "occurred_at": signal.occurred_at.isoformat(),
            "attachment_id": signal.attachment_id,
            "resolution": (
                {
                    "id": resolution.id,
                    "resolution_type": resolution.resolution_type,
                    "reason": resolution.reason,
                    "resolved_at": resolution.resolved_at.isoformat(),
                }
                if resolution
                else None
            ),
        }

    def _risk_summary(self, party_id: int) -> dict[str, Any]:
        rows = self.repo.risk_signals(party_id)
        return enterprise_risk_summary(
            (signal.severity, signal.category) for signal, resolution in rows if resolution is None
        )

    def list_risk_signals(self, party_id: int) -> dict[str, Any]:
        self._require_risk("party:risk_read")
        self._organization(party_id)
        rows = self.repo.risk_signals(party_id)
        return {
            "summary": enterprise_risk_summary(
                (signal.severity, signal.category)
                for signal, resolution in rows
                if resolution is None
            ),
            "items": [self._risk_dict(signal, resolution) for signal, resolution in rows],
        }

    def create_risk_signal(self, party_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self._require_risk("party:risk_manage")
        self._organization(party_id, write=True)
        category = enum_value(data.get("category"), RISK_CATEGORIES, "category")
        severity = enum_value(data.get("severity"), RISK_SEVERITIES, "severity")
        source_type = enum_value(
            data.get("source_type"), SOURCE_TYPES, "source_type", default="MANUAL"
        )
        if source_type != "MANUAL":
            raise AppError("外部风险提供商未连接", code="PROVIDER_NOT_CONNECTED", status_code=503)
        source_reference = optional_text(
            data.get("source_reference"), "source_reference", max_length=128
        )
        if source_reference:
            existing = self.repo.risk_signal_by_source(party_id, source_type, source_reference)
            if existing is not None:
                resolution = self.repo.resolution(existing.id)
                return self._risk_dict(existing, resolution)
        attachment_id = data.get("attachment_id")
        if attachment_id is not None:
            self._validate_evidence_attachment(party_id, int(attachment_id))
        occurred_at = data.get("occurred_at") or utc_now()
        row = self._insert_or_conflict(
            lambda: self.repo.add_risk_signal(
                {
                    "party_id": party_id,
                    "category": category,
                    "severity": severity,
                    "summary": required_text(data.get("summary"), "summary", max_length=1000),
                    "source_type": source_type,
                    "source_reference": source_reference,
                    "occurred_at": occurred_at,
                    "attachment_id": int(attachment_id) if attachment_id is not None else None,
                    "created_by": self.ctx.user_id or None,
                }
            ),
            code="ENTERPRISE_RISK_SOURCE_CONFLICT",
            message="风险来源事件已存在",
        )
        self.audit.record(
            action="create",
            resource_type="PARTY_ENTERPRISE_RISK_SIGNAL",
            resource_id=row.id,
            park_id=self._park_id(party_id),
            detail={
                "party_id": party_id,
                "category": category,
                "severity": severity,
                "source_type": source_type,
                "attachment_id": attachment_id,
            },
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_RISK_SIGNAL_CREATED",
            source_type="PARTY_ENTERPRISE_RISK_SIGNAL",
            source_id=row.id,
            payload={"category": category, "severity": severity},
            generation=1,
        )
        self._commit_or_conflict("ENTERPRISE_RISK_SOURCE_CONFLICT", "风险来源事件已存在")
        return self._risk_dict(row, None)

    def resolve_risk_signal(
        self,
        party_id: int,
        signal_id: int,
        *,
        resolution_type: str,
        reason: str,
    ) -> dict[str, Any]:
        self._require_risk("party:risk_manage")
        self._organization(party_id, write=True)
        signal = self.repo.risk_signal(signal_id, party_id, for_update=True)
        if signal is None:
            raise AppError("企业风险信号不存在", code="ENTERPRISE_RISK_NOT_FOUND", status_code=404)
        existing = self.repo.resolution(signal_id)
        if existing is not None:
            return self._risk_dict(signal, existing)
        target = enum_value(resolution_type, RISK_RESOLUTION_TYPES, "resolution_type")
        resolution = self._insert_or_conflict(
            lambda: self.repo.add_resolution(
                {
                    "party_id": party_id,
                    "signal_id": signal_id,
                    "resolution_type": target,
                    "reason": required_text(reason, "reason", max_length=1000),
                    "resolved_by": self.ctx.user_id or None,
                    "resolved_at": utc_now(),
                }
            ),
            code="ENTERPRISE_RISK_ALREADY_RESOLVED",
            message="风险信号已被处理",
        )
        self.audit.record(
            action="resolve",
            resource_type="PARTY_ENTERPRISE_RISK_SIGNAL",
            resource_id=signal.id,
            park_id=self._park_id(party_id),
            detail={"party_id": party_id, "resolution_type": target},
        )
        self._event(
            party_id=party_id,
            event_type="PARTY_ENTERPRISE_RISK_SIGNAL_RESOLVED",
            source_type="PARTY_ENTERPRISE_RISK_SIGNAL",
            source_id=signal.id,
            payload={"resolution_type": target},
            generation=resolution.id,
        )
        self._commit_or_conflict("ENTERPRISE_RISK_ALREADY_RESOLVED", "风险信号已被处理")
        return self._risk_dict(signal, resolution)
