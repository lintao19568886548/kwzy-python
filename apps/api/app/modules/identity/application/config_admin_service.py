"""功能说明：组织 / 字典 / 系统参数管理。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.identity.infrastructure.config_admin_repository import ConfigAdminRepository


class ConfigAdminService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ConfigAdminRepository(session)

    def list_org_units(self, *, tenant_id: int) -> list[dict]:
        return [self._org_dict(r) for r in self.repo.list_org_units(tenant_id)]

    def create_org_unit(self, *, tenant_id: int, data: dict) -> dict:
        code = str(data.get("code") or "").strip()
        name = str(data.get("name") or "").strip()
        if not code or not name:
            raise AppError("code/name 必填", code="VALIDATION_ERROR", status_code=400)
        if self.repo.find_org_by_code(tenant_id, code):
            raise AppError("组织编码重复", code="ORG_CODE_DUPLICATE", status_code=409)
        parent_id = data.get("parent_id")
        if parent_id is not None:
            p = self.repo.get_org(int(parent_id))
            if p is None or int(p.tenant_id) != tenant_id:
                raise AppError("上级组织不存在", code="ORG_PARENT_NOT_FOUND", status_code=404)
        row = self.repo.create_org(
            tenant_id=tenant_id,
            parent_id=int(parent_id) if parent_id is not None else None,
            code=code,
            name=name,
            sort_order=int(data.get("sort_order") or 0),
            status=str(data.get("status") or "ACTIVE"),
            remark=data.get("remark"),
        )
        self.session.commit()
        return self._org_dict(row)

    def update_org_unit(self, *, tenant_id: int, org_id: int, data: dict) -> dict:
        row = self.repo.get_org(org_id)
        if row is None or int(row.tenant_id) != tenant_id:
            raise AppError("组织不存在", code="ORG_NOT_FOUND", status_code=404)
        if "name" in data and data["name"] is not None:
            row.name = str(data["name"]).strip()
        if "sort_order" in data and data["sort_order"] is not None:
            row.sort_order = int(data["sort_order"])
        if "status" in data and data["status"] is not None:
            row.status = str(data["status"])
        if "remark" in data:
            row.remark = data.get("remark")
        if "parent_id" in data:
            pid = data.get("parent_id")
            if pid is not None and int(pid) == int(org_id):
                raise AppError("上级不能是自身", code="VALIDATION_ERROR", status_code=400)
            row.parent_id = int(pid) if pid is not None else None
        self.session.add(row)
        self.session.commit()
        return self._org_dict(row)

    def _org_dict(self, row) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "parent_id": row.parent_id,
            "code": row.code,
            "name": row.name,
            "sort_order": row.sort_order,
            "status": row.status,
            "remark": row.remark,
        }

    def list_dict_types(self, *, tenant_id: int) -> list[dict]:
        return [
            {"id": r.id, "code": r.code, "name": r.name, "status": r.status, "remark": r.remark}
            for r in self.repo.list_dict_types(tenant_id)
        ]

    def create_dict_type(self, *, tenant_id: int, data: dict) -> dict:
        code = str(data.get("code") or "").strip()
        name = str(data.get("name") or "").strip()
        if not code or not name:
            raise AppError("code/name 必填", code="VALIDATION_ERROR", status_code=400)
        if self.repo.find_dict_type(tenant_id, code):
            raise AppError("字典类型编码重复", code="DICT_TYPE_DUPLICATE", status_code=409)
        row = self.repo.create_dict_type(
            tenant_id=tenant_id,
            code=code,
            name=name,
            status=str(data.get("status") or "ACTIVE"),
            remark=data.get("remark"),
        )
        self.session.commit()
        return {"id": row.id, "code": row.code, "name": row.name, "status": row.status}

    def list_dict_items(self, *, tenant_id: int, type_code: str) -> list[dict]:
        dt = self.repo.find_dict_type(tenant_id, type_code)
        if dt is None:
            raise AppError("字典类型不存在", code="DICT_TYPE_NOT_FOUND", status_code=404)
        return [
            {
                "id": r.id,
                "dict_type_id": r.dict_type_id,
                "item_label": r.item_label,
                "item_value": r.item_value,
                "sort_order": r.sort_order,
                "status": r.status,
            }
            for r in self.repo.list_dict_items(tenant_id, int(dt.id))
        ]

    def create_dict_item(self, *, tenant_id: int, type_code: str, data: dict) -> dict:
        dt = self.repo.find_dict_type(tenant_id, type_code)
        if dt is None:
            raise AppError("字典类型不存在", code="DICT_TYPE_NOT_FOUND", status_code=404)
        label = str(data.get("item_label") or "").strip()
        value = str(data.get("item_value") or "").strip()
        if not label or not value:
            raise AppError("item_label/item_value 必填", code="VALIDATION_ERROR", status_code=400)
        row = self.repo.create_dict_item(
            tenant_id=tenant_id,
            dict_type_id=int(dt.id),
            item_label=label,
            item_value=value,
            sort_order=int(data.get("sort_order") or 0),
            status=str(data.get("status") or "ACTIVE"),
            remark=data.get("remark"),
        )
        self.session.commit()
        return {
            "id": row.id,
            "dict_type_id": row.dict_type_id,
            "item_label": row.item_label,
            "item_value": row.item_value,
            "sort_order": row.sort_order,
            "status": row.status,
        }

    def list_params(self, *, tenant_id: int) -> list[dict]:
        return [self._param_dict(r, mask_secret=True) for r in self.repo.list_params(tenant_id)]

    def upsert_param(self, *, tenant_id: int, data: dict) -> dict:
        key = str(data.get("param_key") or "").strip()
        if not key:
            raise AppError("param_key 必填", code="VALIDATION_ERROR", status_code=400)
        value = data.get("param_value")
        if value is None:
            raise AppError("param_value 必填", code="VALIDATION_ERROR", status_code=400)
        row = self.repo.find_param(tenant_id, key)
        if row is None:
            row = self.repo.create_param(
                tenant_id=tenant_id,
                param_key=key,
                param_value=str(value),
                value_type=str(data.get("value_type") or "STRING"),
                is_secret=bool(data.get("is_secret") or False),
                remark=data.get("remark"),
            )
        else:
            row.param_value = str(value)
            if data.get("value_type") is not None:
                row.value_type = str(data["value_type"])
            if data.get("is_secret") is not None:
                row.is_secret = bool(data["is_secret"])
            if "remark" in data:
                row.remark = data.get("remark")
            self.session.add(row)
            self.session.flush()
        self.session.commit()
        return self._param_dict(row, mask_secret=True)

    def get_param(self, *, tenant_id: int, param_key: str) -> dict:
        row = self.repo.find_param(tenant_id, param_key)
        if row is None:
            raise AppError("参数不存在", code="PARAM_NOT_FOUND", status_code=404)
        return self._param_dict(row, mask_secret=True)

    def _param_dict(self, row, *, mask_secret: bool) -> dict:
        value = row.param_value
        if mask_secret and row.is_secret:
            value = "******"
        return {
            "id": row.id,
            "param_key": row.param_key,
            "param_value": value,
            "value_type": row.value_type,
            "is_secret": row.is_secret,
            "remark": row.remark,
        }
