"""Versioned asset-template application service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.park_property.domain.asset_templates import (
    BUILTIN_TEMPLATES,
    normalize_category,
    validate_attributes,
    validate_field_schema,
)
from app.modules.park_property.infrastructure.asset_template_repository import (
    AssetTemplateRepository,
)
from app.shared.tenant_context import TenantContext


class AssetTemplateService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = AssetTemplateRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def ensure_builtins(self) -> None:
        existing = {row.code for row in self.repo.list_all()}
        for definition in BUILTIN_TEMPLATES:
            if definition["code"] in existing:
                continue
            fields, defaults, checksum = validate_field_schema(definition["fields"], {})
            try:
                # A savepoint makes tenant bootstrap safe when two first requests race.
                with self.session.begin_nested():
                    template = self.repo.create_template(
                        code=definition["code"],
                        name=definition["name"],
                        category=definition["category"],
                        description="系统内置业态模板，可通过新版本扩展字段",
                        status="ACTIVE",
                        is_builtin=True,
                        current_version=1,
                        lock_version=1,
                        created_by=self.ctx.user_id or None,
                        updated_by=self.ctx.user_id or None,
                    )
                    self.repo.create_version(
                        template_id=template.id,
                        version=1,
                        status="PUBLISHED",
                        field_schema_json=fields,
                        defaults_json=defaults,
                        schema_checksum=checksum,
                        created_by=self.ctx.user_id or None,
                        published_by=self.ctx.user_id or None,
                        published_at=datetime.utcnow(),
                    )
            except IntegrityError:
                # The database uniqueness constraint proves another request won.
                continue
            existing.add(definition["code"])

    def list_templates(self) -> list[dict[str, Any]]:
        self.ensure_builtins()
        self.session.commit()
        return [self._template_dict(row) for row in self.repo.list_all()]

    def get_template(self, template_id: int) -> dict[str, Any]:
        self.ensure_builtins()
        template = self.repo.get_by_id(template_id)
        if template is None:
            raise AppError("资产模板不存在", code="ASSET_TEMPLATE_NOT_FOUND", status_code=404)
        return self._template_dict(template, include_versions=True)

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        code = str(data.get("code") or "").strip().upper()
        name = str(data.get("name") or "").strip()
        if not code or len(code) > 64 or not name:
            raise AppError("模板编码和名称必填", code="VALIDATION_ERROR", status_code=400)
        if self.repo.find_code(code):
            raise AppError("模板编码已存在", code="ASSET_TEMPLATE_CODE_CONFLICT", status_code=409)
        try:
            category = normalize_category(data.get("category"))
            fields, defaults, checksum = validate_field_schema(
                data.get("fields") or [], data.get("defaults") or {}
            )
        except ValueError as exc:
            raise AppError(str(exc), code="ASSET_TEMPLATE_INVALID", status_code=400) from exc
        try:
            template = self.repo.create_template(
                code=code,
                name=name,
                category=category,
                description=data.get("description"),
                status="ACTIVE",
                is_builtin=False,
                current_version=0,
                lock_version=1,
                created_by=self.ctx.user_id or None,
                updated_by=self.ctx.user_id or None,
            )
            self.repo.create_version(
                template_id=template.id,
                version=1,
                status="DRAFT",
                field_schema_json=fields,
                defaults_json=defaults,
                schema_checksum=checksum,
                created_by=self.ctx.user_id or None,
            )
            self.audit.record(
                action="create",
                resource_type="ASSET_TEMPLATE",
                resource_id=template.id,
                detail={"code": code, "category": category},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "模板编码已存在", code="ASSET_TEMPLATE_CODE_CONFLICT", status_code=409
            ) from exc
        return self._template_dict(template, include_versions=True)

    def update_draft(self, template_id: int, data: dict[str, Any]) -> dict[str, Any]:
        template = self._locked(template_id, int(data["expected_version"]))
        draft = self.repo.draft(template_id)
        if draft is None:
            raise AppError(
                "当前没有可编辑草稿", code="ASSET_TEMPLATE_DRAFT_NOT_FOUND", status_code=409
            )
        try:
            if data.get("name") is not None and not str(data["name"]).strip():
                raise ValueError("模板名称不能为空")
            fields, defaults, checksum = validate_field_schema(
                data.get("fields", draft.field_schema_json),
                data.get("defaults", draft.defaults_json),
            )
            if data.get("category") is not None:
                template.category = normalize_category(data["category"])
        except ValueError as exc:
            raise AppError(str(exc), code="ASSET_TEMPLATE_INVALID", status_code=400) from exc
        if data.get("name") is not None:
            template.name = str(data["name"]).strip()
        if data.get("description") is not None:
            template.description = data["description"]
        draft.field_schema_json = fields
        draft.defaults_json = defaults
        draft.schema_checksum = checksum
        template.lock_version += 1
        template.updated_by = self.ctx.user_id or None
        self.repo.save(template)
        self.audit.record(
            action="update_draft",
            resource_type="ASSET_TEMPLATE",
            resource_id=template.id,
            detail={"draft_version": draft.version},
        )
        self.session.commit()
        return self._template_dict(template, include_versions=True)

    def publish(self, template_id: int, expected_version: int) -> dict[str, Any]:
        template = self._locked(template_id, expected_version)
        draft = self.repo.draft(template_id)
        if draft is None:
            raise AppError(
                "当前没有可发布草稿", code="ASSET_TEMPLATE_DRAFT_NOT_FOUND", status_code=409
            )
        try:
            fields, defaults, checksum = validate_field_schema(
                draft.field_schema_json, draft.defaults_json
            )
        except ValueError as exc:
            raise AppError(str(exc), code="ASSET_TEMPLATE_INVALID", status_code=400) from exc
        previous = self.repo.published(template_id)
        if previous is not None:
            previous.status = "RETIRED"
        draft.field_schema_json = fields
        draft.defaults_json = defaults
        draft.schema_checksum = checksum
        draft.status = "PUBLISHED"
        draft.published_by = self.ctx.user_id or None
        draft.published_at = datetime.utcnow()
        template.current_version = draft.version
        template.lock_version += 1
        template.updated_by = self.ctx.user_id or None
        self.repo.save(template)
        self.audit.record(
            action="publish",
            resource_type="ASSET_TEMPLATE",
            resource_id=template.id,
            detail={"version": draft.version, "checksum": checksum},
        )
        self.session.commit()
        return self._template_dict(template, include_versions=True)

    def new_draft(self, template_id: int, expected_version: int) -> dict[str, Any]:
        template = self._locked(template_id, expected_version)
        if self.repo.draft(template_id) is not None:
            raise AppError("已存在草稿", code="ASSET_TEMPLATE_DRAFT_EXISTS", status_code=409)
        published = self.repo.published(template_id)
        if published is None:
            raise AppError(
                "没有已发布版本可复制", code="ASSET_TEMPLATE_NOT_PUBLISHED", status_code=409
            )
        self.repo.create_version(
            template_id=template.id,
            version=max(template.current_version, published.version) + 1,
            status="DRAFT",
            field_schema_json=published.field_schema_json,
            defaults_json=published.defaults_json,
            schema_checksum=published.schema_checksum,
            created_by=self.ctx.user_id or None,
        )
        template.lock_version += 1
        self.repo.save(template)
        self.audit.record(
            action="new_draft",
            resource_type="ASSET_TEMPLATE",
            resource_id=template.id,
            detail={"from_version": published.version},
        )
        self.session.commit()
        return self._template_dict(template, include_versions=True)

    def retire(self, template_id: int, expected_version: int) -> dict[str, Any]:
        template = self._locked(template_id, expected_version)
        template.status = "RETIRED"
        template.lock_version += 1
        self.repo.save(template)
        self.audit.record(action="retire", resource_type="ASSET_TEMPLATE", resource_id=template.id)
        self.session.commit()
        return self._template_dict(template, include_versions=True)

    def resolve_and_validate(
        self, *, template_version_id: int | None, usage_type: object, attributes: object
    ) -> tuple[Any, Any, dict[str, Any]]:
        self.ensure_builtins()
        try:
            category = normalize_category(usage_type)
        except ValueError as exc:
            raise AppError(str(exc), code="ASSET_CATEGORY_INVALID", status_code=400) from exc
        pair = (
            self.repo.template_for_version(template_version_id)
            if template_version_id
            else self.repo.published_by_category(category)
        )
        if pair is None:
            raise AppError(
                "没有可用的已发布资产模板", code="ASSET_TEMPLATE_NOT_PUBLISHED", status_code=409
            )
        template, version = pair
        if template.category != category:
            raise AppError(
                "资产模板类别与单元业态不一致",
                code="ASSET_TEMPLATE_CATEGORY_MISMATCH",
                status_code=400,
            )
        if template.status != "ACTIVE" or version.status != "PUBLISHED":
            raise AppError(
                "资产模板版本不可用于新单元", code="ASSET_TEMPLATE_NOT_PUBLISHED", status_code=409
            )
        try:
            merged = dict(version.defaults_json or {})
            merged.update(attributes or {})
            validated = validate_attributes(merged, version.field_schema_json or [])
        except ValueError as exc:
            raise AppError(str(exc), code="ASSET_ATTRIBUTES_INVALID", status_code=400) from exc
        return template, version, validated

    def public_version(self, version_id: int | None) -> dict[str, Any] | None:
        if version_id is None:
            return None
        pair = self.repo.template_for_version(version_id)
        if pair is None:
            return None
        template, version = pair
        return {
            "template_id": template.id,
            "template_code": template.code,
            "template_name": template.name,
            "category": template.category,
            "version_id": version.id,
            "version": version.version,
            "fields": version.field_schema_json,
            "checksum": version.schema_checksum,
        }

    def _locked(self, template_id: int, expected: int) -> Any:
        template = self.repo.get_for_update(template_id)
        if template is None:
            raise AppError("资产模板不存在", code="ASSET_TEMPLATE_NOT_FOUND", status_code=404)
        if template.lock_version != expected:
            raise AppError(
                "资产模板版本已变化", code="ASSET_TEMPLATE_VERSION_CONFLICT", status_code=409
            )
        return template

    def _template_dict(self, template: Any, *, include_versions: bool = False) -> dict[str, Any]:
        versions = self.repo.versions(template.id)
        current = next(
            (
                row
                for row in versions
                if row.status == "PUBLISHED" and row.version == template.current_version
            ),
            None,
        )
        draft = next((row for row in versions if row.status == "DRAFT"), None)
        result: dict[str, Any] = {
            "id": template.id,
            "code": template.code,
            "name": template.name,
            "category": template.category,
            "description": template.description,
            "status": template.status,
            "is_builtin": template.is_builtin,
            "current_version": template.current_version,
            "lock_version": template.lock_version,
            "published": self._version_dict(current) if current else None,
            "draft": self._version_dict(draft) if draft else None,
        }
        if include_versions:
            result["versions"] = [self._version_dict(row) for row in versions]
        return result

    @staticmethod
    def _version_dict(version: Any) -> dict[str, Any]:
        return {
            "id": version.id,
            "version": version.version,
            "status": version.status,
            "fields": version.field_schema_json,
            "defaults": version.defaults_json,
            "schema_checksum": version.schema_checksum,
            "published_at": version.published_at.isoformat() if version.published_at else None,
        }
