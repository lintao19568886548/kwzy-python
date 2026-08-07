"""Park application service.

功能说明：
    园区 CRUD 编排；仅操作领域实体，经 Mapper/Repository 持久化。

业务职责：
    Application 层；禁止直接构造 ORM Model。
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.modules.park_property.domain.entities import ParkEntity
from app.modules.park_property.domain.states import assert_park_status
from app.modules.park_property.infrastructure.mappers import ParkMapper
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class ParkService:
    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.repo = ParkRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def list_parks(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        offset = (page - 1) * page_size
        items = self.repo.list(
            offset=offset, limit=page_size, keyword=keyword, status=status
        )
        total = self.repo.count(keyword=keyword, status=status)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(ParkMapper.to_entity(p)) for p in items],
        }

    def get_park(self, park_id: int) -> dict[str, Any]:
        park = self.repo.get_by_id(park_id)
        if park is None:
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        return self._to_dict(ParkMapper.to_entity(park))

    def create_park(self, data: dict[str, Any]) -> dict[str, Any]:
        name = (data.get("name") or "").strip()
        if not name:
            raise AppError("园区名称必填", code="VALIDATION_ERROR", status_code=400)
        try:
            status = assert_park_status(data.get("status") or "ACTIVE")
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc

        entity = ParkEntity(
            tenant_id=self.ctx.tenant_id,
            name=name,
            address=(data.get("address") or "").strip(),
            area=Decimal(str(data.get("area") or 0)),
            contact=data.get("contact"),
            manager=data.get("manager"),
            description=data.get("description"),
            status=status,
        )
        model = ParkMapper.new_model(entity)
        self.repo.add(model)
        self.audit.record(
            action="create",
            resource_type="PARK",
            resource_id=model.id,
            park_id=model.id,
            detail={"status": model.status},
        )
        self.session.commit()
        self.session.refresh(model)
        log_business_success(
            logger,
            "创建园区成功",
            ctx=self.ctx,
            module="park",
            action="create",
            resource_id=model.id,
            park_id=model.id,
        )
        return self._to_dict(ParkMapper.to_entity(model))

    def update_park(self, park_id: int, data: dict[str, Any]) -> dict[str, Any]:
        model = self.repo.get_by_id(park_id)
        if model is None:
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        entity = ParkMapper.to_entity(model)

        if "name" in data and data["name"] is not None:
            name = str(data["name"]).strip()
            if not name:
                raise AppError("园区名称不能为空", code="VALIDATION_ERROR", status_code=400)
            entity.name = name
        if "address" in data and data["address"] is not None:
            entity.address = str(data["address"])
        if "area" in data and data["area"] is not None:
            entity.area = Decimal(str(data["area"]))
        if "contact" in data:
            entity.contact = data["contact"]
        if "manager" in data:
            entity.manager = data["manager"]
        if "description" in data:
            entity.description = data["description"]
        if "status" in data and data["status"] is not None:
            try:
                entity.status = assert_park_status(str(data["status"]))
            except ValueError as exc:
                raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc

        ParkMapper.apply_entity(model, entity)
        self.repo.save(model)
        self.audit.record(
            action="update",
            resource_type="PARK",
            resource_id=model.id,
            park_id=model.id,
            detail={"fields": sorted(data.keys()), "status": model.status},
        )
        self.session.commit()
        self.session.refresh(model)
        log_business_success(
            logger,
            "更新园区成功",
            ctx=self.ctx,
            module="park",
            action="update",
            resource_id=model.id,
            park_id=model.id,
        )
        return self._to_dict(ParkMapper.to_entity(model))

    def delete_park(self, park_id: int) -> None:
        model = self.repo.get_by_id(park_id)
        if model is None:
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        self.repo.soft_delete(model)
        self.audit.record(
            action="delete",
            resource_type="PARK",
            resource_id=model.id,
            park_id=model.id,
            detail={"soft_delete": True},
        )
        self.session.commit()
        log_business_success(
            logger,
            "删除园区成功",
            ctx=self.ctx,
            module="park",
            action="delete",
            resource_id=model.id,
            park_id=model.id,
        )

    @staticmethod
    def _to_dict(entity: ParkEntity) -> dict[str, Any]:
        return {
            "id": entity.id,
            "tenant_id": entity.tenant_id,
            "name": entity.name,
            "address": entity.address,
            "area": float(entity.area or 0),
            "contact": entity.contact,
            "manager": entity.manager,
            "description": entity.description,
            "status": entity.status,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
