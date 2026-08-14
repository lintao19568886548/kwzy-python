from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.database.models.park_property import AssetTemplate, AssetTemplateVersion
from app.infrastructure.database.repository_base import TenantParkRepositoryBase


class AssetTemplateRepository(TenantParkRepositoryBase[AssetTemplate]):
    model = AssetTemplate
    uses_soft_delete = False

    def create_template(self, **values) -> AssetTemplate:
        template = AssetTemplate(tenant_id=self.tenant_id, **values)
        self.add(template)
        return template

    def create_version(self, *, template_id: int, **values) -> AssetTemplateVersion:
        return self.add_version(
            AssetTemplateVersion(
                tenant_id=self.tenant_id,
                template_id=template_id,
                **values,
            )
        )

    def list_all(self) -> list[AssetTemplate]:
        stmt = self._base_select().order_by(AssetTemplate.category, AssetTemplate.code)
        return list(self.session.scalars(stmt).all())

    def find_code(self, code: str) -> AssetTemplate | None:
        return self.session.scalars(self._base_select().where(AssetTemplate.code == code)).first()

    def get_for_update(self, template_id: int) -> AssetTemplate | None:
        return self.session.scalars(
            self._base_select().where(AssetTemplate.id == template_id).with_for_update()
        ).first()

    def versions(self, template_id: int) -> list[AssetTemplateVersion]:
        stmt = (
            select(AssetTemplateVersion)
            .where(
                AssetTemplateVersion.tenant_id == self.tenant_id,
                AssetTemplateVersion.template_id == template_id,
            )
            .order_by(AssetTemplateVersion.version.desc())
        )
        return list(self.session.scalars(stmt).all())

    def draft(self, template_id: int) -> AssetTemplateVersion | None:
        stmt = select(AssetTemplateVersion).where(
            AssetTemplateVersion.tenant_id == self.tenant_id,
            AssetTemplateVersion.template_id == template_id,
            AssetTemplateVersion.status == "DRAFT",
        )
        return self.session.scalars(stmt).first()

    def published(self, template_id: int) -> AssetTemplateVersion | None:
        stmt = (
            select(AssetTemplateVersion)
            .where(
                AssetTemplateVersion.tenant_id == self.tenant_id,
                AssetTemplateVersion.template_id == template_id,
                AssetTemplateVersion.status == "PUBLISHED",
            )
            .order_by(AssetTemplateVersion.version.desc())
        )
        return self.session.scalars(stmt).first()

    def get_version(
        self, version_id: int, *, published_only: bool = False
    ) -> AssetTemplateVersion | None:
        stmt = select(AssetTemplateVersion).where(
            AssetTemplateVersion.tenant_id == self.tenant_id,
            AssetTemplateVersion.id == version_id,
        )
        if published_only:
            stmt = stmt.where(AssetTemplateVersion.status == "PUBLISHED")
        return self.session.scalars(stmt).first()

    def add_version(self, version: AssetTemplateVersion) -> AssetTemplateVersion:
        version.tenant_id = self.tenant_id
        self.session.add(version)
        self.session.flush()
        return version

    def template_for_version(
        self, version_id: int
    ) -> tuple[AssetTemplate, AssetTemplateVersion] | None:
        stmt = (
            select(AssetTemplate, AssetTemplateVersion)
            .join(AssetTemplateVersion, AssetTemplateVersion.template_id == AssetTemplate.id)
            .where(
                AssetTemplate.tenant_id == self.tenant_id,
                AssetTemplateVersion.tenant_id == self.tenant_id,
                AssetTemplateVersion.id == version_id,
            )
        )
        return self.session.execute(stmt).first()

    def published_by_category(
        self, category: str
    ) -> tuple[AssetTemplate, AssetTemplateVersion] | None:
        stmt = (
            select(AssetTemplate, AssetTemplateVersion)
            .join(AssetTemplateVersion, AssetTemplateVersion.template_id == AssetTemplate.id)
            .where(
                AssetTemplate.tenant_id == self.tenant_id,
                AssetTemplate.category == category,
                AssetTemplate.status == "ACTIVE",
                AssetTemplateVersion.version == AssetTemplate.current_version,
                AssetTemplateVersion.status == "PUBLISHED",
            )
            .order_by(AssetTemplate.is_builtin.desc(), AssetTemplate.id)
        )
        return self.session.execute(stmt).first()

    def public_versions(
        self, version_ids: set[int]
    ) -> dict[int, tuple[AssetTemplate, AssetTemplateVersion]]:
        if not version_ids:
            return {}
        stmt = (
            select(AssetTemplate, AssetTemplateVersion)
            .join(AssetTemplateVersion, AssetTemplateVersion.template_id == AssetTemplate.id)
            .where(
                AssetTemplate.tenant_id == self.tenant_id,
                AssetTemplateVersion.tenant_id == self.tenant_id,
                AssetTemplateVersion.id.in_(version_ids),
            )
        )
        return {
            int(version.id): (template, version)
            for template, version in self.session.execute(stmt).all()
        }
