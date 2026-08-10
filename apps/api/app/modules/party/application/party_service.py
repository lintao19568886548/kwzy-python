"""功能说明：
    Party 应用服务：编排主档与子资源用例。

业务职责：
    Application 层；事务、权限、审计与领域规则协调，不直接暴露 HTTP。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_logging import log_business_success
from app.core.errors import AppError
from app.infrastructure.database.audit import AuditRecorder
from app.infrastructure.database.base import utc_now
from app.modules.park_property.infrastructure.park_repository import ParkRepository
from app.modules.party.domain.entities import (
    PartyAddressEntity,
    PartyContactEntity,
    PartyEntity,
    PartyParkRelationEntity,
    PartyRiskEventEntity,
    PartyRoleEntity,
)
from app.modules.party.domain.rules import (
    assert_address_type,
    assert_party_type,
    assert_role_code,
    assert_status_transition,
    is_person_address_forbidden,
    normalize_credit_code,
    validate_credit_code_format,
)
from app.modules.party.infrastructure.mappers import (
    PartyAddressMapper,
    PartyContactMapper,
    PartyMapper,
    PartyParkRelationMapper,
    PartyRiskEventMapper,
    PartyRoleMapper,
)
from app.modules.party.infrastructure.party_repository import (
    PartyAddressRepository,
    PartyContactRepository,
    PartyParkRelationRepository,
    PartyRepository,
    PartyRiskEventRepository,
    PartyRoleRepository,
)
from app.shared.tenant_context import TenantContext

logger = logging.getLogger(__name__)


def _mask_phone(phone: str | None) -> str | None:
    """功能说明：
        对手机号做简单脱敏，供审计 detail 使用。
    """

    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]


class PartyService:
    """功能说明：
        编排 Party 主档与子资源用例。

    业务职责：
        应用层；协调仓储、领域规则、审计与事务；tenant 来自 TenantContext。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.parties = PartyRepository(session, ctx)
        self.roles = PartyRoleRepository(session, ctx)
        self.relations = PartyParkRelationRepository(session, ctx)
        self.contacts = PartyContactRepository(session, ctx)
        self.addresses = PartyAddressRepository(session, ctx)
        self.risks = PartyRiskEventRepository(session, ctx)
        self.parks = ParkRepository(session, ctx)
        self.audit = AuditRecorder(session, ctx)

    def _require_visible(self, party_id: int):
        """功能说明：
            按租户与园区可见性加载 Party，不可见视为不存在。

        业务职责：
            私有守卫；统一 404 语义，避免跨租户/跨 scope 信息泄露。

        输入参数：
            party_id：主体 ID。

        返回结果：
            可见的 Party ORM。

        异常说明：
            AppError(PARTY_NOT_FOUND, 404)：不存在或不可见。

        业务规则：
            使用仓储 get_by_id（含 park scope）。
        """

        model = self.parties.get_by_id(party_id)
        if model is None:
            raise AppError("主体不存在", code="PARTY_NOT_FOUND", status_code=404)
        return model

    def _reject_person_address_access(self, party) -> None:
        """功能说明：
            v1 拒绝 PERSON 主体全部地址读写（含列表/详情）。

        业务职责：
            在 Application 层强制执行，避免仅 Router 拦截被其他入口绕过。
            即使库中已有 PERSON 地址行，也不得读取或返回任何地址字段、数量或摘要。
            不引入临时 party:pii:* 权限；未来由独立 KMS/PII change 替换。

        输入参数：
            party：已加载主体（含 party_type）。

        返回结果：
            None。

        异常说明：
            AppError(PERSON_ADDRESS_FORBIDDEN, 403)：party_type 为 PERSON。

        业务规则：
            ORGANIZATION 不拒绝；错误消息不得包含地址字段值。
        """

        if is_person_address_forbidden(party.party_type):
            raise AppError(
                "PERSON 主体地址在 v1 禁止访问",
                code="PERSON_ADDRESS_FORBIDDEN",
                status_code=403,
            )

    def _assert_can_write_party(self, model) -> None:
        """功能说明：
            校验对已关联/未关联主体的写权限。

        业务职责：
            私有权限守卫。

        输入参数：
            model：主体 ORM。

        返回结果：
            None。

        异常说明：
            AppError(PERMISSION_DENIED, 403)：缺少 write 或 manage_unscoped。

        业务规则：
            1. 无 ACTIVE 园区关系 → 需要 party:manage_unscoped。
            2. 有关系 → 需要 party:write。
        """

        has_rel = self.parties.has_active_relations(model.id)
        if not has_rel:
            if not self.ctx.has_permission("party:manage_unscoped"):
                raise AppError(
                    "无未关联园区主体管理权限",
                    code="PERMISSION_DENIED",
                    status_code=403,
                )
            return
        if not self.ctx.has_permission("party:write"):
            raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

    def _to_dict(self, model, *, include_risk_reason: bool = False) -> dict[str, Any]:
        """功能说明：
            将主体 ORM 序列化为 API 字典（不含地址）。
        """

        e = PartyMapper.to_entity(model)
        data: dict[str, Any] = {
            "id": e.id,
            "tenant_id": e.tenant_id,
            "party_type": e.party_type,
            "name": e.name,
            "contact_name": e.contact_name,
            "contact_phone": e.contact_phone,
            "credit_code": e.credit_code,
            "status": e.status,
            "risk_status": e.risk_status,
            "remark": e.remark,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        }
        if include_risk_reason and self.ctx.has_permission("party:risk_read"):
            data["blacklist_reason"] = e.blacklist_reason
        return data

    def list_parties(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        risk_status: Optional[str] = None,
        party_type: Optional[str] = None,
        include_archived: bool = False,
        park_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """功能说明：
            分页列出当前租户下可见主体。

        业务职责：
            应用层查询用例；委托仓储施加 tenant + park scope。

        输入参数：
            page/page_size：分页（page≥1，page_size 上限 200）。
            keyword/status/risk_status/party_type/include_archived/park_id：筛选。

        返回结果：
            {total, page, page_size, items}；items 不含 addresses。

        异常说明：
            无（权限由路由 party:read 保证）。

        业务规则：
            1. tenant_id 来自上下文。
            2. 默认排除 ARCHIVED（除非指定 status 或 include_archived）。
            3. 不嵌入地址。
        """

        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        offset = (page - 1) * page_size
        items = self.parties.list(
            offset=offset,
            limit=page_size,
            keyword=keyword,
            status=status,
            risk_status=risk_status,
            party_type=party_type,
            include_archived=include_archived,
            park_id=park_id,
        )
        total = self.parties.count(
            keyword=keyword,
            status=status,
            risk_status=risk_status,
            party_type=party_type,
            include_archived=include_archived,
            park_id=park_id,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._to_dict(p) for p in items],
        }

    def get_party(self, party_id: int) -> dict[str, Any]:
        """功能说明：
            获取可见主体详情（含角色与有效园区关系）。

        业务职责：
            应用层详情用例。

        输入参数：
            party_id：主体 ID。

        返回结果：
            主档字典 + roles + ACTIVE park_relations；不含 addresses。

        异常说明：
            AppError(PARTY_NOT_FOUND, 404)。

        业务规则：
            1. 可见性 = tenant + park scope。
            2. blacklist_reason 仅 party:risk_read 可见。
            3. PERSON/ORGANIZATION 均不嵌套地址。
        """

        model = self._require_visible(party_id)
        data = self._to_dict(model, include_risk_reason=True)
        data["roles"] = [
            {
                "id": r.id,
                "role_code": r.role_code,
                "status": r.status,
            }
            for r in self.roles.list_for_party(party_id)
        ]
        data["park_relations"] = [
            {
                "id": rel.id,
                "park_id": rel.park_id,
                "party_role_id": rel.party_role_id,
                "status": rel.status,
            }
            for rel in self.relations.list_for_party(party_id)
            if rel.status == "ACTIVE"
        ]
        return data

    def create_party(self, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：
            在当前租户创建主体，可选初始园区关系。

        业务职责：
            应用层创建用例；规范化 credit_code、写审计并提交事务。

        输入参数：
            data：含 name/party_type/credit_code/initial_park_relation 等。

        返回结果：
            创建后详情（get_party）。

        异常说明：
            VALIDATION_ERROR：名称为空或类型非法。
            PERMISSION_DENIED：无 write/manage_unscoped。
            CREDIT_CODE_INVALID / CREDIT_CODE_DUPLICATE / CREDIT_CODE_ARCHIVED_EXISTS。
            PARTY_PARK_RELATION_DUPLICATE / PARK_NOT_FOUND / PARK_SCOPE_DENIED。

        业务规则：
            1. tenant_id 仅来自 TenantContext。
            2. 无 initial_park_relation 需 party:manage_unscoped。
            3. 信用代码租户内唯一（含归档占用策略）。
        """

        name = (data.get("name") or "").strip()
        if not name:
            raise AppError("名称必填", code="VALIDATION_ERROR", status_code=400)
        try:
            party_type = assert_party_type(data.get("party_type") or "ORGANIZATION")
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc

        initial = data.get("initial_park_relation")
        if not initial and not self.ctx.has_permission("party:manage_unscoped"):
            raise AppError(
                "创建未关联园区主体需要 party:manage_unscoped",
                code="PERMISSION_DENIED",
                status_code=403,
            )
        if initial and not (
            self.ctx.has_permission("party:write") or self.ctx.has_permission("party:manage_unscoped")
        ):
            raise AppError("无操作权限", code="PERMISSION_DENIED", status_code=403)

        credit = normalize_credit_code(data.get("credit_code"))
        try:
            validate_credit_code_format(credit)
        except ValueError as exc:
            raise AppError(str(exc), code="CREDIT_CODE_INVALID", status_code=400) from exc
        if credit:
            existing = self.parties.find_by_credit_code(credit)
            if existing:
                if existing.status == "ARCHIVED":
                    raise AppError(
                        "信用代码已被已归档主体占用，请恢复该主体",
                        code="CREDIT_CODE_ARCHIVED_EXISTS",
                        status_code=409,
                    )
                raise AppError("信用代码重复", code="CREDIT_CODE_DUPLICATE", status_code=409)

        entity = PartyEntity(
            tenant_id=self.ctx.tenant_id,
            name=name,
            party_type=party_type,
            contact_name=data.get("contact_name"),
            contact_phone=data.get("contact_phone"),
            credit_code=credit,
            status="ACTIVE",
            risk_status="NORMAL",
            remark=data.get("remark"),
        )
        model = PartyMapper.new_model(entity)
        try:
            self.parties.add(model)
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("信用代码重复", code="CREDIT_CODE_DUPLICATE", status_code=409) from exc

        if initial:
            park_id = int(initial["park_id"])
            role_id = initial.get("party_role_id")
            role_code = initial.get("role_code")
            resolved_role_id: int | None = None
            if role_id is not None:
                role = self.roles.get(int(role_id), model.id)
                if role is None:
                    raise AppError(
                        "party_role_id 无效",
                        code="PARTY_ROLE_MISMATCH",
                        status_code=400,
                    )
                resolved_role_id = int(role.id)
            else:
                rc = assert_role_code(role_code or "LESSEE")
                role_model = PartyRoleMapper.new_model(
                    PartyRoleEntity(
                        tenant_id=self.ctx.tenant_id,
                        party_id=model.id,
                        role_code=rc,
                        status="ACTIVE",
                        started_at=utc_now(),
                    )
                )
                self.roles.add(role_model)
                resolved_role_id = int(role_model.id)
            self._assert_park_exists_and_scope(park_id)
            rel = PartyParkRelationMapper.new_model(
                PartyParkRelationEntity(
                    tenant_id=self.ctx.tenant_id,
                    party_id=model.id,
                    park_id=park_id,
                    party_role_id=int(resolved_role_id),
                    status="ACTIVE",
                    started_at=utc_now(),
                )
            )
            try:
                self.relations.add(rel)
            except IntegrityError as exc:
                self.session.rollback()
                raise AppError(
                    "园区关系重复",
                    code="PARTY_PARK_RELATION_DUPLICATE",
                    status_code=409,
                ) from exc

        self.audit.record(
            action="create",
            resource_type="PARTY",
            resource_id=model.id,
            detail={"party_type": model.party_type, "status": model.status},
        )
        self.session.commit()
        self.session.refresh(model)
        log_business_success(
            logger,
            "创建主体成功",
            ctx=self.ctx,
            module="party",
            action="create",
            resource_id=model.id,
        )
        return self.get_party(model.id)

    def update_party(self, party_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：
            部分更新可见主体字段。

        业务职责：
            应用层更新用例；信用代码冲突与状态机校验。

        输入参数：
            party_id：主体 ID。
            data：待更新字段字典（exclude_unset 语义由上层保证）。

        返回结果：
            更新后详情。

        异常说明：
            PARTY_NOT_FOUND / PERMISSION_DENIED / VALIDATION_ERROR /
            CREDIT_CODE_* / PARTY_STATUS_INVALID / PARTY_RISK_INVALID。

        业务规则：
            1. 需写权限（关联/未关联规则）。
            2. 禁止经本方法改 risk_status。
            3. 状态迁移走 assert_status_transition。
        """

        model = self._require_visible(party_id)
        self._assert_can_write_party(model)
        entity = PartyMapper.to_entity(model)
        if "name" in data and data["name"] is not None:
            name = str(data["name"]).strip()
            if not name:
                raise AppError("名称不能为空", code="VALIDATION_ERROR", status_code=400)
            entity.name = name
        if "contact_name" in data:
            entity.contact_name = data["contact_name"]
        if "contact_phone" in data:
            entity.contact_phone = data["contact_phone"]
        if "remark" in data:
            entity.remark = data["remark"]
        if "party_type" in data and data["party_type"] is not None:
            entity.party_type = assert_party_type(str(data["party_type"]))
        if "credit_code" in data:
            credit = normalize_credit_code(data["credit_code"])
            try:
                validate_credit_code_format(credit)
            except ValueError as exc:
                raise AppError(str(exc), code="CREDIT_CODE_INVALID", status_code=400) from exc
            if credit and credit != entity.credit_code:
                existing = self.parties.find_by_credit_code(credit)
                if existing and existing.id != model.id:
                    if existing.status == "ARCHIVED":
                        raise AppError(
                            "信用代码已被已归档主体占用",
                            code="CREDIT_CODE_ARCHIVED_EXISTS",
                            status_code=409,
                        )
                    raise AppError("信用代码重复", code="CREDIT_CODE_DUPLICATE", status_code=409)
            entity.credit_code = credit
        if "status" in data and data["status"] is not None:
            # direct status patch limited; prefer archive/restore
            try:
                entity.status = assert_status_transition(entity.status, str(data["status"]))
            except ValueError as exc:
                raise AppError(str(exc), code="PARTY_STATUS_INVALID", status_code=400) from exc
        # reject risk_status via generic update
        if "risk_status" in data and data["risk_status"] is not None:
            raise AppError(
                "请使用 blacklist/remove-blacklist 接口变更风险状态",
                code="PARTY_RISK_INVALID",
                status_code=400,
            )
        PartyMapper.apply_entity(model, entity)
        try:
            self.parties.save(model)
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("信用代码重复", code="CREDIT_CODE_DUPLICATE", status_code=409) from exc
        self.audit.record(
            action="update",
            resource_type="PARTY",
            resource_id=model.id,
            detail={"fields": sorted(data.keys())},
        )
        self.session.commit()
        self.session.refresh(model)
        log_business_success(
            logger,
            "更新主体成功",
            ctx=self.ctx,
            module="party",
            action="update",
            resource_id=model.id,
        )
        return self.get_party(model.id)

    def archive_party(self, party_id: int) -> dict[str, Any]:
        """功能说明：
            将主体归档为 ARCHIVED。

        业务职责：
            应用层生命周期用例。

        输入参数：
            party_id：主体 ID。

        返回结果：
            归档后详情。

        异常说明：
            PARTY_NOT_FOUND / PERMISSION_DENIED / PARTY_STATUS_INVALID。

        业务规则：
            状态机允许后仅改 status；不物理删除地址等子资源。
        """

        model = self._require_visible(party_id)
        self._assert_can_write_party(model)
        try:
            assert_status_transition(model.status, "ARCHIVED")
        except ValueError as exc:
            raise AppError(str(exc), code="PARTY_STATUS_INVALID", status_code=400) from exc
        model.status = "ARCHIVED"
        self.parties.save(model)
        self.audit.record(action="archive", resource_type="PARTY", resource_id=model.id, detail={})
        self.session.commit()
        log_business_success(
            logger, "归档主体成功", ctx=self.ctx, module="party", action="archive", resource_id=model.id
        )
        return self.get_party(model.id)

    def restore_party(self, party_id: int, *, target_status: str = "ACTIVE") -> dict[str, Any]:
        """功能说明：
            从 ARCHIVED 恢复主体。

        业务职责：
            应用层恢复用例；校验信用代码冲突。

        输入参数：
            party_id：主体 ID。
            target_status：目标状态，默认 ACTIVE。

        返回结果：
            恢复后详情。

        异常说明：
            PARTY_STATUS_INVALID / CREDIT_CODE_DUPLICATE / PERMISSION_DENIED。

        业务规则：
            1. 不清除 risk_status/黑名单字段。
            2. 信用代码与非归档主体冲突则拒绝。
        """

        model = self.parties.get_raw_by_id(party_id)
        if model is None or model.status != "ARCHIVED":
            # still apply visibility
            model = self._require_visible(party_id)
            if model.status != "ARCHIVED":
                raise AppError("主体未归档", code="PARTY_STATUS_INVALID", status_code=400)
        self._assert_can_write_party(model)
        try:
            target = assert_status_transition("ARCHIVED", target_status)
        except ValueError as exc:
            raise AppError(str(exc), code="PARTY_STATUS_INVALID", status_code=400) from exc
        if model.credit_code:
            other = self.parties.find_by_credit_code(model.credit_code)
            if other and other.id != model.id and other.status != "ARCHIVED":
                raise AppError(
                    "恢复失败：信用代码与现有主体冲突",
                    code="CREDIT_CODE_DUPLICATE",
                    status_code=409,
                )
        model.status = target
        self.parties.save(model)
        self.audit.record(
            action="restore",
            resource_type="PARTY",
            resource_id=model.id,
            detail={"status": target, "risk_status": model.risk_status},
        )
        self.session.commit()
        log_business_success(
            logger, "恢复主体成功", ctx=self.ctx, module="party", action="restore", resource_id=model.id
        )
        return self.get_party(model.id)

    # ----- roles -----
    def list_roles(self, party_id: int) -> list[dict[str, Any]]:
        """功能说明：
            列出主体业务角色。

        业务职责：
            应用层查询。

        输入参数：
            party_id：主体 ID。

        返回结果：
            角色摘要列表。

        异常说明：
            PARTY_NOT_FOUND。

        业务规则：
            主体须可见。
        """

        self._require_visible(party_id)
        return [
            {
                "id": r.id,
                "party_id": r.party_id,
                "role_code": r.role_code,
                "status": r.status,
            }
            for r in self.roles.list_for_party(party_id)
        ]

    def add_role(self, party_id: int, role_code: str) -> dict[str, Any]:
        """功能说明：
            新增业务角色或重新激活已有角色码。

        业务职责：
            应用层写用例。

        输入参数：
            party_id：主体 ID。
            role_code：业务角色码。

        返回结果：
            {id, role_code, status}。

        异常说明：
            PARTY_NOT_FOUND / PERMISSION_DENIED / VALIDATION_ERROR。

        业务规则：
            需写权限；ACTIVE 重复则拒绝。
        """

        model = self._require_visible(party_id)
        self._assert_can_write_party(model)
        code = assert_role_code(role_code)
        existing = self.roles.find_active_code(party_id, code)
        if existing and existing.status == "ACTIVE":
            raise AppError("角色已存在", code="VALIDATION_ERROR", status_code=400)
        if existing:
            existing.status = "ACTIVE"
            existing.ended_at = None
            self.roles.save(existing)
            role = existing
        else:
            role = self.roles.add(
                PartyRoleMapper.new_model(
                    PartyRoleEntity(
                        tenant_id=self.ctx.tenant_id,
                        party_id=party_id,
                        role_code=code,
                        status="ACTIVE",
                        started_at=utc_now(),
                    )
                )
            )
        self.audit.record(
            action="add_role",
            resource_type="PARTY_ROLE",
            resource_id=role.id,
            detail={"role_code": code, "party_id": party_id},
        )
        self.session.commit()
        return {"id": role.id, "role_code": role.role_code, "status": role.status}

    def deactivate_role(self, party_id: int, role_id: int) -> dict[str, Any]:
        """功能说明：
            停用业务角色。

        业务职责：
            应用层写用例；占用检查。

        输入参数：
            party_id：主体 ID。
            role_id：角色 ID。

        返回结果：
            角色摘要。

        异常说明：
            VALIDATION_ERROR(404) / PARTY_ROLE_IN_USE(409) / PERMISSION_DENIED。

        业务规则：
            仍有 ACTIVE 园区关系则不可停用。
        """

        model = self._require_visible(party_id)
        self._assert_can_write_party(model)
        role = self.roles.get(role_id, party_id)
        if role is None:
            raise AppError("角色不存在", code="VALIDATION_ERROR", status_code=404)
        if self.roles.count_active_relations(role.id) > 0:
            raise AppError(
                "角色仍有有效园区关系，请先结束关系",
                code="PARTY_ROLE_IN_USE",
                status_code=409,
            )
        role.status = "INACTIVE"
        role.ended_at = utc_now()
        self.roles.save(role)
        self.audit.record(
            action="deactivate_role",
            resource_type="PARTY_ROLE",
            resource_id=role.id,
            detail={"party_id": party_id},
        )
        self.session.commit()
        return {"id": role.id, "role_code": role.role_code, "status": role.status}

    # ----- park relations -----
    def list_relations(self, party_id: int) -> list[dict[str, Any]]:
        """功能说明：
            列出主体园区关系。

        业务职责：
            应用层查询。

        输入参数：
            party_id：主体 ID。

        返回结果：
            关系摘要列表。

        异常说明：
            PARTY_NOT_FOUND。

        业务规则：
            主体须可见。
        """

        self._require_visible(party_id)
        return [
            {
                "id": r.id,
                "park_id": r.park_id,
                "party_role_id": r.party_role_id,
                "status": r.status,
            }
            for r in self.relations.list_for_party(party_id)
        ]

    def _assert_park_exists_and_scope(self, park_id: int) -> None:
        """功能说明：
            校验园区存在于租户且调用方具备园区数据权限。

        业务职责：
            私有守卫。

        输入参数：
            park_id：园区 ID。

        返回结果：
            None。

        异常说明：
            PARK_NOT_FOUND / PARK_SCOPE_DENIED。

        业务规则：
            manage_unscoped 可绕过 allows_park 限制（用于分配关系）。
        """

        if not self.parks.exists_in_tenant(park_id):
            raise AppError("园区不存在", code="PARK_NOT_FOUND", status_code=404)
        if not self.ctx.allows_park(park_id) and not self.ctx.has_permission(
            "party:manage_unscoped"
        ):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)

    def add_relation(self, party_id: int, park_id: int, party_role_id: int) -> dict[str, Any]:
        """功能说明：
            为可见主体添加 ACTIVE 园区关系。

        业务职责：
            应用层写用例；首关联权限与 scope 校验。

        输入参数：
            party_id：主体 ID。
            park_id：园区 ID。
            party_role_id：本主体下 ACTIVE 角色 ID。

        返回结果：
            关系摘要。

        异常说明：
            PERMISSION_DENIED / PARTY_ROLE_MISMATCH / PARK_* /
            PARTY_PARK_RELATION_DUPLICATE。

        业务规则：
            1. 无任何 ACTIVE 关系时需 party:manage_unscoped。
            2. party_role_id 必须属于该主体且 ACTIVE。
            3. tenant 强制。
        """

        model = self._require_visible(party_id)
        has_rel = self.parties.has_active_relations(party_id)
        if not has_rel:
            if not self.ctx.has_permission("party:manage_unscoped"):
                raise AppError(
                    "分配首个园区关系需要 party:manage_unscoped",
                    code="PERMISSION_DENIED",
                    status_code=403,
                )
        else:
            self._assert_can_write_party(model)
        role = self.roles.get(party_role_id, party_id)
        if role is None or role.status != "ACTIVE":
            raise AppError("party_role_id 无效或不属于该主体", code="PARTY_ROLE_MISMATCH", status_code=400)
        self._assert_park_exists_and_scope(park_id)
        if self.relations.find_active(party_id, park_id, party_role_id):
            raise AppError("园区关系重复", code="PARTY_PARK_RELATION_DUPLICATE", status_code=409)
        rel_model = PartyParkRelationMapper.new_model(
            PartyParkRelationEntity(
                tenant_id=self.ctx.tenant_id,
                party_id=party_id,
                park_id=park_id,
                party_role_id=party_role_id,
                status="ACTIVE",
                started_at=utc_now(),
            )
        )
        try:
            self.relations.add(rel_model)
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError(
                "园区关系重复",
                code="PARTY_PARK_RELATION_DUPLICATE",
                status_code=409,
            ) from exc
        self.audit.record(
            action="add_park_relation",
            resource_type="PARTY_PARK_RELATION",
            resource_id=rel_model.id,
            park_id=park_id,
            detail={"party_id": party_id, "party_role_id": party_role_id},
        )
        self.session.commit()
        log_business_success(
            logger,
            "添加园区关系成功",
            ctx=self.ctx,
            module="party",
            action="add_park_relation",
            resource_id=rel_model.id,
            park_id=park_id,
        )
        return {
            "id": rel_model.id,
            "park_id": rel_model.park_id,
            "party_role_id": rel_model.party_role_id,
            "status": rel_model.status,
        }

    def end_relation(self, party_id: int, relation_id: int) -> dict[str, Any]:
        """功能说明：
            结束园区关系（status=ENDED）。

        业务职责：
            应用层写用例。

        输入参数：
            party_id：主体 ID。
            relation_id：关系 ID。

        返回结果：
            {id, status}。

        异常说明：
            VALIDATION_ERROR(404) / PERMISSION_DENIED。

        业务规则：
            relation 须属于 path party 与当前租户。
        """

        model = self._require_visible(party_id)
        self._assert_can_write_party(model)
        rel = self.relations.get(relation_id, party_id)
        if rel is None:
            raise AppError("关系不存在", code="VALIDATION_ERROR", status_code=404)
        rel.status = "ENDED"
        rel.ended_at = utc_now()
        self.relations.save(rel)
        self.audit.record(
            action="end_park_relation",
            resource_type="PARTY_PARK_RELATION",
            resource_id=rel.id,
            park_id=rel.park_id,
            detail={"party_id": party_id},
        )
        self.session.commit()
        return {"id": rel.id, "status": rel.status}

    # ----- contacts -----
    def list_contacts(self, party_id: int) -> list[dict[str, Any]]:
        """功能说明：
            列出主体联系人。

        业务职责：
            应用层查询。

        输入参数：
            party_id：主体 ID。

        返回结果：
            联系人字段列表。

        异常说明：
            PARTY_NOT_FOUND。

        业务规则：
            主体须可见。
        """

        self._require_visible(party_id)
        return [
            {
                "id": c.id,
                "party_id": c.party_id,
                "name": c.name,
                "phone": c.phone,
                "email": c.email,
                "role_label": c.role_label,
                "is_primary": c.is_primary,
            }
            for c in self.contacts.list_for_party(party_id)
        ]

    def create_contact(self, party_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：
            创建联系人；主联系人同步主档 contact_*。

        业务职责：
            应用层写用例；审计手机号脱敏。

        输入参数：
            party_id：主体 ID。
            data：联系人字段。

        返回结果：
            {id, name, phone, is_primary}。

        异常说明：
            PARTY_NOT_FOUND / PERMISSION_DENIED。

        业务规则：
            is_primary 时清除其他 primary。
        """

        model = self._require_visible(party_id)
        self._assert_can_write_party(model)
        is_primary = bool(data.get("is_primary"))
        if is_primary:
            self.contacts.clear_primary(party_id)
        c = PartyContactMapper.new_model(
            PartyContactEntity(
                tenant_id=self.ctx.tenant_id,
                party_id=party_id,
                name=data.get("name"),
                phone=data.get("phone"),
                email=data.get("email"),
                role_label=data.get("role_label"),
                is_primary=is_primary,
            )
        )
        self.contacts.add(c)
        if is_primary and c.phone:
            model.contact_phone = c.phone
            model.contact_name = c.name
            self.parties.save(model)
        self.audit.record(
            action="create_contact",
            resource_type="PARTY_CONTACT",
            resource_id=c.id,
            detail={"party_id": party_id, "phone": _mask_phone(c.phone)},
        )
        self.session.commit()
        return {
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "is_primary": c.is_primary,
        }

    def update_contact(self, party_id: int, contact_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：
            更新联系人。

        业务职责：
            应用层写用例。

        输入参数：
            party_id/contact_id：归属双重键。
            data：部分字段。

        返回结果：
            {id, is_primary, phone}。

        异常说明：
            CONTACT_NOT_FOUND / PERMISSION_DENIED。

        业务规则：
            contact 必须属于 party_id。
        """

        model = self._require_visible(party_id)
        self._assert_can_write_party(model)
        c = self.contacts.get(contact_id, party_id)
        if c is None:
            raise AppError("联系人不存在", code="CONTACT_NOT_FOUND", status_code=404)
        if data.get("is_primary"):
            self.contacts.clear_primary(party_id)
            c.is_primary = True
        if "name" in data:
            c.name = data["name"]
        if "phone" in data:
            c.phone = data["phone"]
        if "email" in data:
            c.email = data["email"]
        if "role_label" in data:
            c.role_label = data["role_label"]
        self.contacts.save(c)
        if c.is_primary:
            model.contact_phone = c.phone
            model.contact_name = c.name
            self.parties.save(model)
        self.audit.record(
            action="update_contact",
            resource_type="PARTY_CONTACT",
            resource_id=c.id,
            detail={"party_id": party_id, "phone": _mask_phone(c.phone)},
        )
        self.session.commit()
        return {"id": c.id, "is_primary": c.is_primary, "phone": c.phone}

    def delete_contact(self, party_id: int, contact_id: int) -> None:
        """功能说明：
            软删除联系人。

        业务职责：
            应用层写用例。

        输入参数：
            party_id/contact_id：归属双重键。

        返回结果：
            None。

        异常说明：
            CONTACT_NOT_FOUND / CONTACT_PRIMARY_REQUIRED。

        业务规则：
            存在其他联系人时不可直接删除主联系人。
        """

        model = self._require_visible(party_id)
        self._assert_can_write_party(model)
        c = self.contacts.get(contact_id, party_id)
        if c is None:
            raise AppError("联系人不存在", code="CONTACT_NOT_FOUND", status_code=404)
        if c.is_primary:
            others = [x for x in self.contacts.list_for_party(party_id) if x.id != c.id]
            if others:
                raise AppError(
                    "删除主联系人须先指定替代或取消 primary",
                    code="CONTACT_PRIMARY_REQUIRED",
                    status_code=400,
                )
        c.is_deleted = True
        c.deleted_at = utc_now()
        c.is_primary = False
        self.contacts.save(c)
        self.audit.record(
            action="delete_contact",
            resource_type="PARTY_CONTACT",
            resource_id=c.id,
            detail={"party_id": party_id, "phone": _mask_phone(c.phone)},
        )
        self.session.commit()

    # ----- addresses -----
    def list_addresses(self, party_id: int) -> list[dict[str, Any]]:
        """功能说明：
            列出主体地址；PERSON 一律 403，且不返回任何地址数据。

        业务职责：
            应用层查询；在查询地址表之前拒绝 PERSON。

        输入参数：
            party_id：主体 ID。

        返回结果：
            ORGANIZATION：地址字段列表；PERSON：不返回（抛错）。

        异常说明：
            PARTY_NOT_FOUND / PERSON_ADDRESS_FORBIDDEN。

        业务规则：
            1. PERSON 全拒绝（含预存行）。
            2. 错误不得含 street/detail 等地址值。
            3. 列表/详情主档路径不调用本方法嵌套。
        """

        party = self._require_visible(party_id)
        # 必须在查询地址表之前拒绝，避免预存 PERSON 地址经 API 泄露
        self._reject_person_address_access(party)
        addrs = self.addresses.list_for_party(party_id)
        return [
            {
                "id": a.id,
                "address_type": a.address_type,
                "country_code": a.country_code,
                "province": a.province,
                "city": a.city,
                "district": a.district,
                "street": a.street,
                "detail": a.detail,
                "postal_code": a.postal_code,
                "is_primary": a.is_primary,
                "status": a.status,
            }
            for a in addrs
        ]

    def create_address(self, party_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：
            创建 ORGANIZATION 地址；PERSON 一律拒绝。

        业务职责：
            应用层写用例；审计不含完整地址正文。

        输入参数：
            party_id：主体 ID。
            data：地址字段。

        返回结果：
            {id, address_type, is_primary}（无 street/detail）。

        异常说明：
            PERSON_ADDRESS_FORBIDDEN / PERMISSION_DENIED /
            VALIDATION_ERROR / ADDRESS_PRIMARY_CONFLICT。

        业务规则：
            1. Application 强制 PERSON 拒绝。
            2. primary 互斥按 address_type。
            3. audit detail 仅 party_id/address_type。
        """

        party = self._require_visible(party_id)
        self._reject_person_address_access(party)
        self._assert_can_write_party(party)
        try:
            at = assert_address_type(str(data.get("address_type") or "OTHER"))
        except ValueError as exc:
            raise AppError(str(exc), code="VALIDATION_ERROR", status_code=400) from exc
        is_primary = bool(data.get("is_primary"))
        if is_primary:
            self.addresses.clear_primary(party_id, at)
        addr = PartyAddressMapper.new_model(
            PartyAddressEntity(
                tenant_id=self.ctx.tenant_id,
                party_id=party_id,
                address_type=at,
                country_code=data.get("country_code"),
                province=data.get("province"),
                city=data.get("city"),
                district=data.get("district"),
                street=data.get("street"),
                detail=data.get("detail"),
                postal_code=data.get("postal_code"),
                is_primary=is_primary,
                status="ACTIVE",
            )
        )
        try:
            self.addresses.add(addr)
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("地址 primary 冲突", code="ADDRESS_PRIMARY_CONFLICT", status_code=409) from exc
        self.audit.record(
            action="create_address",
            resource_type="PARTY_ADDRESS",
            resource_id=addr.id,
            detail={"party_id": party_id, "address_type": at},
        )
        self.session.commit()
        log_business_success(
            logger,
            "创建地址成功",
            ctx=self.ctx,
            module="party",
            action="create_address",
            resource_id=addr.id,
        )
        return {"id": addr.id, "address_type": addr.address_type, "is_primary": addr.is_primary}

    def update_address(self, party_id: int, address_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """功能说明：
            更新 ORGANIZATION 地址；PERSON 一律拒绝。

        业务职责：
            应用层写用例；先拒绝 PERSON 再查库。

        输入参数：
            party_id/address_id：归属双重键。
            data：部分字段。

        返回结果：
            {id, is_primary}。

        异常说明：
            PERSON_ADDRESS_FORBIDDEN / ADDRESS_NOT_FOUND /
            ADDRESS_PRIMARY_CONFLICT / PERMISSION_DENIED。

        业务规则：
            address 必须属于 party_id 与当前租户。
        """

        party = self._require_visible(party_id)
        self._reject_person_address_access(party)
        self._assert_can_write_party(party)
        addr = self.addresses.get(address_id, party_id)
        if addr is None:
            raise AppError("地址不存在", code="ADDRESS_NOT_FOUND", status_code=404)
        if data.get("is_primary"):
            self.addresses.clear_primary(party_id, addr.address_type)
            addr.is_primary = True
        for field in (
            "country_code",
            "province",
            "city",
            "district",
            "street",
            "detail",
            "postal_code",
            "status",
        ):
            if field in data:
                setattr(addr, field, data[field])
        try:
            self.addresses.save(addr)
        except IntegrityError as exc:
            self.session.rollback()
            raise AppError("地址 primary 冲突", code="ADDRESS_PRIMARY_CONFLICT", status_code=409) from exc
        self.audit.record(
            action="update_address",
            resource_type="PARTY_ADDRESS",
            resource_id=addr.id,
            detail={"party_id": party_id, "address_type": addr.address_type},
        )
        self.session.commit()
        return {"id": addr.id, "is_primary": addr.is_primary}

    def delete_address(self, party_id: int, address_id: int) -> None:
        """功能说明：
            软删 ORGANIZATION 地址；PERSON 一律拒绝。

        业务职责：
            应用层写用例。

        输入参数：
            party_id/address_id：归属双重键。

        返回结果：
            None。

        异常说明：
            PERSON_ADDRESS_FORBIDDEN / ADDRESS_NOT_FOUND / PERMISSION_DENIED。

        业务规则：
            软删除；PERSON 在查库前 403。
        """

        party = self._require_visible(party_id)
        self._reject_person_address_access(party)
        self._assert_can_write_party(party)
        addr = self.addresses.get(address_id, party_id)
        if addr is None:
            raise AppError("地址不存在", code="ADDRESS_NOT_FOUND", status_code=404)
        addr.deleted_at = utc_now()
        addr.is_primary = False
        self.addresses.save(addr)
        self.audit.record(
            action="delete_address",
            resource_type="PARTY_ADDRESS",
            resource_id=addr.id,
            detail={"party_id": party_id},
        )
        self.session.commit()

    # ----- risk -----
    def list_risk_events(self, party_id: int) -> list[dict[str, Any]]:
        """功能说明：
            列出主体风险事件。

        业务职责：
            应用层查询；需 party:risk_read。

        输入参数：
            party_id：主体 ID。

        返回结果：
            事件字段列表。

        异常说明：
            PARTY_NOT_FOUND / PERMISSION_DENIED。

        业务规则：
            主体须可见；事件只读不可改。
        """

        self._require_visible(party_id)
        if not self.ctx.has_permission("party:risk_read"):
            raise AppError("无风险读取权限", code="PERMISSION_DENIED", status_code=403)
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "previous_risk_status": e.previous_risk_status,
                "new_risk_status": e.new_risk_status,
                "reason": e.reason,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in self.risks.list_for_party(party_id)
        ]

    def blacklist(self, party_id: int, reason: str) -> dict[str, Any]:
        """功能说明：
            将主体加入黑名单并追加风险事件。

        业务职责：
            应用层风险用例；同事务审计。

        输入参数：
            party_id：主体 ID。
            reason：原因必填。

        返回结果：
            更新后主体详情。

        异常说明：
            PERMISSION_DENIED / PARTY_RISK_REASON_REQUIRED / PARTY_RISK_INVALID。

        业务规则：
            需 party:risk_manage；不可重复拉黑。
        """

        if not self.ctx.has_permission("party:risk_manage"):
            raise AppError("无风险管理权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require_visible(party_id)
        reason = (reason or "").strip()
        if not reason:
            raise AppError("黑名单原因必填", code="PARTY_RISK_REASON_REQUIRED", status_code=400)
        if model.risk_status == "BLACKLISTED":
            raise AppError("主体已在黑名单", code="PARTY_RISK_INVALID", status_code=400)
        prev = model.risk_status
        model.risk_status = "BLACKLISTED"
        model.blacklist_reason = reason
        model.blacklisted_at = utc_now()
        model.blacklisted_by = self.ctx.user_id
        model.blacklist_removed_at = None
        model.blacklist_removed_by = None
        self.parties.save(model)
        ev = PartyRiskEventMapper.new_model(
            PartyRiskEventEntity(
                tenant_id=self.ctx.tenant_id,
                party_id=party_id,
                event_type="BLACKLISTED",
                previous_risk_status=prev,
                new_risk_status="BLACKLISTED",
                reason=reason,
                operator_user_id=self.ctx.user_id,
                request_id=self.ctx.request_id,
                source="API",
                occurred_at=utc_now(),
            )
        )
        self.risks.add(ev)
        self.audit.record(
            action="blacklist",
            resource_type="PARTY",
            resource_id=party_id,
            detail={"event_id": ev.id},
        )
        self.session.commit()
        log_business_success(
            logger, "主体加入黑名单", ctx=self.ctx, module="party", action="blacklist", resource_id=party_id
        )
        return self.get_party(party_id)

    def remove_blacklist(self, party_id: int, reason: str) -> dict[str, Any]:
        """功能说明：
            解除主体黑名单并追加风险事件。

        业务职责：
            应用层风险用例；同事务审计。

        输入参数：
            party_id：主体 ID。
            reason：解除原因必填。

        返回结果：
            更新后主体详情。

        异常说明：
            PERMISSION_DENIED / PARTY_RISK_REASON_REQUIRED / PARTY_RISK_INVALID。

        业务规则：
            需 party:risk_manage；仅 BLACKLISTED 可解除。
        """

        if not self.ctx.has_permission("party:risk_manage"):
            raise AppError("无风险管理权限", code="PERMISSION_DENIED", status_code=403)
        model = self._require_visible(party_id)
        reason = (reason or "").strip()
        if not reason:
            raise AppError("解除原因必填", code="PARTY_RISK_REASON_REQUIRED", status_code=400)
        if model.risk_status != "BLACKLISTED":
            raise AppError("主体不在黑名单", code="PARTY_RISK_INVALID", status_code=400)
        prev = model.risk_status
        model.risk_status = "NORMAL"
        model.blacklist_removed_at = utc_now()
        model.blacklist_removed_by = self.ctx.user_id
        self.parties.save(model)
        ev = PartyRiskEventMapper.new_model(
            PartyRiskEventEntity(
                tenant_id=self.ctx.tenant_id,
                party_id=party_id,
                event_type="BLACKLIST_REMOVED",
                previous_risk_status=prev,
                new_risk_status="NORMAL",
                reason=reason,
                operator_user_id=self.ctx.user_id,
                request_id=self.ctx.request_id,
                source="API",
                occurred_at=utc_now(),
            )
        )
        self.risks.add(ev)
        self.audit.record(
            action="remove_blacklist",
            resource_type="PARTY",
            resource_id=party_id,
            detail={"event_id": ev.id},
        )
        self.session.commit()
        log_business_success(
            logger,
            "主体解除黑名单",
            ctx=self.ctx,
            module="party",
            action="remove_blacklist",
            resource_id=party_id,
        )
        return self.get_party(party_id)
