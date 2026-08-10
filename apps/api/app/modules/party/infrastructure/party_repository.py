"""功能说明：
    Party 持久化仓储（含 tenant 与 park 可见性）。

业务职责：
    Infrastructure 层；强制租户隔离与园区 scope，不暴露 HTTP。
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.party import (
    Party,
    PartyAddress,
    PartyContact,
    PartyParkRelation,
    PartyRiskEvent,
    PartyRole,
)
from app.shared.tenant_context import ParkScopeMode, TenantContext


class PartyRepository:
    """功能说明：
        Party 主档仓储，强制 tenant 与可见性规则。

    业务职责：
        Infrastructure；列表/计数/按 ID 加载均叠加 park scope。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        """功能说明：
            当前租户 ID（来自 TenantContext）。

        业务职责：
            快捷属性；禁止信任客户端伪造 tenant。

        输入参数：
            无。

        返回结果：
            int 租户主键。

        异常说明：
            无。

        业务规则：
            始终等于 ctx.tenant_id。
        """

        return self.ctx.tenant_id

    def has_active_relations(self, party_id: int) -> bool:
        """功能说明：
            判断主体是否存在未删除的 ACTIVE 园区关系。

        业务职责：
            供写权限分支（关联主体 vs 未关联主体）。

        输入参数：
            party_id：主体 ID。

        返回结果：
            True 表示至少一条有效关系。

        异常说明：
            无。

        业务规则：
            仅统计当前 tenant；status=ACTIVE 且 deleted_at 为空。
        """

        stmt = select(func.count()).select_from(PartyParkRelation).where(
            PartyParkRelation.tenant_id == self.tenant_id,
            PartyParkRelation.party_id == party_id,
            PartyParkRelation.status == "ACTIVE",
            PartyParkRelation.deleted_at.is_(None),
        )
        return int(self.session.scalar(stmt) or 0) > 0

    def _visible_filter(self, stmt):
        """功能说明：
            对 Party 查询施加 tenant 与 park scope 可见性。

        业务职责：
            私有过滤；ALL/LIST/NONE 与 manage_unscoped 组合。

        输入参数：
            stmt：已含 Party 的 Select。

        返回结果：
            叠加过滤后的 stmt。

        异常说明：
            无。

        业务规则：
            1. 始终 tenant_id = 当前租户。
            2. ALL：租户内全部可见。
            3. LIST：仅关联到 park_ids 的主体；有 manage_unscoped 时另含无关系主体。
            4. NONE：默认不可见；有 manage_unscoped 时仅无关系主体。
        """

        stmt = stmt.where(Party.tenant_id == self.tenant_id)
        if self.ctx.park_scope_mode == ParkScopeMode.ALL:
            return stmt
        active_rel = (
            select(PartyParkRelation.party_id)
            .where(
                PartyParkRelation.tenant_id == self.tenant_id,
                PartyParkRelation.status == "ACTIVE",
                PartyParkRelation.deleted_at.is_(None),
            )
            .distinct()
        )
        if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
            scoped = active_rel.where(PartyParkRelation.park_id.in_(self.ctx.park_ids))
            if self.ctx.has_permission("party:manage_unscoped"):
                no_rel = ~exists(
                    select(PartyParkRelation.id).where(
                        PartyParkRelation.tenant_id == self.tenant_id,
                        PartyParkRelation.party_id == Party.id,
                        PartyParkRelation.status == "ACTIVE",
                        PartyParkRelation.deleted_at.is_(None),
                    )
                )
                return stmt.where(or_(Party.id.in_(scoped), no_rel))
            return stmt.where(Party.id.in_(scoped))
        # NONE
        if self.ctx.has_permission("party:manage_unscoped"):
            no_rel = ~exists(
                select(PartyParkRelation.id).where(
                    PartyParkRelation.tenant_id == self.tenant_id,
                    PartyParkRelation.party_id == Party.id,
                    PartyParkRelation.status == "ACTIVE",
                    PartyParkRelation.deleted_at.is_(None),
                )
            )
            return stmt.where(no_rel)
        return stmt.where(False)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        risk_status: Optional[str] = None,
        party_type: Optional[str] = None,
        include_archived: bool = False,
        park_id: Optional[int] = None,
    ) -> Sequence[Party]:
        """功能说明：
            分页列出当前可见主体。

        业务职责：
            查询主档；叠加可见性与筛选条件。

        输入参数：
            offset/limit：分页。
            keyword：名称/电话/信用代码模糊。
            status/risk_status/party_type：精确过滤。
            include_archived：False 时默认排除 ARCHIVED。
            park_id：限定存在该园 ACTIVE 关系的主体。

        返回结果：
            Party ORM 序列（按 id 降序）。

        异常说明：
            无。

        业务规则：
            1. 必须经 _visible_filter（tenant + park scope）。
            2. 不返回地址子资源。
        """

        stmt = select(Party)
        stmt = self._visible_filter(stmt)
        if not include_archived and status is None:
            stmt = stmt.where(Party.status != "ARCHIVED")
        if status:
            stmt = stmt.where(Party.status == status)
        if risk_status:
            stmt = stmt.where(Party.risk_status == risk_status)
        if party_type:
            stmt = stmt.where(Party.party_type == party_type)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Party.name.ilike(like) if hasattr(Party.name, "ilike") else Party.name.like(like),
                    Party.contact_phone.like(like),
                    Party.credit_code.like(like),
                )
            )
        if park_id is not None:
            stmt = stmt.where(
                Party.id.in_(
                    select(PartyParkRelation.party_id).where(
                        PartyParkRelation.tenant_id == self.tenant_id,
                        PartyParkRelation.park_id == int(park_id),
                        PartyParkRelation.status == "ACTIVE",
                        PartyParkRelation.deleted_at.is_(None),
                    )
                )
            )
        stmt = stmt.order_by(Party.id.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def count(
        self,
        *,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        risk_status: Optional[str] = None,
        party_type: Optional[str] = None,
        include_archived: bool = False,
        park_id: Optional[int] = None,
    ) -> int:
        """功能说明：
            统计当前可见主体数量（与 list 同过滤）。

        业务职责：
            分页 total。

        输入参数：
            与 list 相同的筛选参数（无 offset/limit）。

        返回结果：
            非负整数。

        异常说明：
            无。

        业务规则：
            过滤语义与 list 一致。
        """

        stmt = select(func.count()).select_from(Party)
        # rebuild filters via subquery of visible ids
        vis = select(Party.id)
        vis = self._visible_filter(vis)
        if not include_archived and status is None:
            vis = vis.where(Party.status != "ARCHIVED")
        if status:
            vis = vis.where(Party.status == status)
        if risk_status:
            vis = vis.where(Party.risk_status == risk_status)
        if party_type:
            vis = vis.where(Party.party_type == party_type)
        if keyword:
            like = f"%{keyword}%"
            vis = vis.where(
                or_(Party.name.like(like), Party.contact_phone.like(like), Party.credit_code.like(like))
            )
        if park_id is not None:
            vis = vis.where(
                Party.id.in_(
                    select(PartyParkRelation.party_id).where(
                        PartyParkRelation.tenant_id == self.tenant_id,
                        PartyParkRelation.park_id == int(park_id),
                        PartyParkRelation.status == "ACTIVE",
                        PartyParkRelation.deleted_at.is_(None),
                    )
                )
            )
        stmt = select(func.count()).select_from(vis.subquery())
        return int(self.session.scalar(stmt) or 0)

    def get_by_id(self, party_id: int, *, for_write: bool = False) -> Optional[Party]:
        """功能说明：
            按 ID 加载对当前用户可见的主体。

        业务职责：
            详情/写前加载；不可见返回 None（上层映射 404）。

        输入参数：
            party_id：主体 ID。
            for_write：保留参数，当前与读路径同可见性。

        返回结果：
            Party 或 None。

        异常说明：
            无。

        业务规则：
            跨租户或 scope 外一律 None，不区分原因。
        """

        stmt = select(Party).where(Party.id == party_id)
        stmt = self._visible_filter(stmt)
        return self.session.scalars(stmt).first()

    def get_raw_by_id(self, party_id: int) -> Optional[Party]:
        """功能说明：
            仅按租户加载主体（不做 park scope）。

        业务职责：
            归档恢复等内部路径；调用方须已鉴权。

        输入参数：
            party_id：主体 ID。

        返回结果：
            本租户内 Party 或 None。

        异常说明：
            无。

        业务规则：
            仍强制 tenant_id，禁止跨租户。
        """

        return self.session.scalars(
            select(Party).where(Party.tenant_id == self.tenant_id, Party.id == party_id)
        ).first()

    def find_by_credit_code(self, credit_code: str) -> Optional[Party]:
        """功能说明：
            按规范化信用代码在本租户查找主体。

        业务职责：
            唯一性预检。

        输入参数：
            credit_code：已规范化代码。

        返回结果：
            Party 或 None。

        异常说明：
            无。

        业务规则：
            仅本 tenant；含 ARCHIVED 行。
        """

        return self.session.scalars(
            select(Party).where(
                Party.tenant_id == self.tenant_id,
                Party.credit_code == credit_code,
            )
        ).first()

    def add(self, model: Party) -> Party:
        """功能说明：
            插入主体并 flush。

        业务职责：
            写入；覆盖 tenant_id 为当前上下文。

        输入参数：
            model：待插入 ORM。

        返回结果：
            flush 后的 model。

        异常说明：
            IntegrityError 由上层捕获映射业务码。

        业务规则：
            tenant_id 强制为 ctx.tenant_id。
        """

        model.tenant_id = self.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: Party) -> Party:
        """功能说明：
            更新已有主体并 flush。

        业务职责：
            持久化变更。

        输入参数：
            model：已托管或待合并 ORM。

        返回结果：
            flush 后的 model。

        异常说明：
            AppError(TENANT_MISMATCH)：model.tenant_id 与上下文不一致。

        业务规则：
            禁止跨租户保存。
        """

        if int(model.tenant_id) != self.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model


class PartyRoleRepository:
    """功能说明：
        Party 业务角色仓储（租户强制）。

    业务职责：
        Infrastructure；角色读写与在用关系计数。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_party(self, party_id: int) -> list[PartyRole]:
        """功能说明：
            列出主体下全部业务角色。

        业务职责：
            查询。

        输入参数：
            party_id：主体 ID。

        返回结果：
            PartyRole 列表。

        异常说明：
            无。

        业务规则：
            强制 tenant_id；调用方须已校验主体可见性。
        """

        return list(
            self.session.scalars(
                select(PartyRole)
                .where(
                    PartyRole.tenant_id == self.ctx.tenant_id,
                    PartyRole.party_id == party_id,
                )
                .order_by(PartyRole.id)
            ).all()
        )

    def get(self, role_id: int, party_id: int) -> Optional[PartyRole]:
        """功能说明：
            按角色 ID + 主体 ID 加载角色。

        业务职责：
            归属校验查询。

        输入参数：
            role_id：角色主键。
            party_id：必须匹配的主体。

        返回结果：
            PartyRole 或 None。

        异常说明：
            无。

        业务规则：
            跨主体角色返回 None。
        """

        return self.session.scalars(
            select(PartyRole).where(
                PartyRole.tenant_id == self.ctx.tenant_id,
                PartyRole.party_id == party_id,
                PartyRole.id == role_id,
            )
        ).first()

    def find_active_code(self, party_id: int, role_code: str) -> Optional[PartyRole]:
        """功能说明：
            按 role_code 查找主体角色行（含非 ACTIVE）。

        业务职责：
            幂等启用/去重。

        输入参数：
            party_id：主体 ID。
            role_code：业务角色码。

        返回结果：
            PartyRole 或 None。

        异常说明：
            无。

        业务规则：
            租户 + party + role_code 定位。
        """

        return self.session.scalars(
            select(PartyRole).where(
                PartyRole.tenant_id == self.ctx.tenant_id,
                PartyRole.party_id == party_id,
                PartyRole.role_code == role_code,
            )
        ).first()

    def count_active_relations(self, party_role_id: int) -> int:
        """功能说明：
            统计角色上仍有效的园区关系数。

        业务职责：
            停用角色前占用检查。

        输入参数：
            party_role_id：角色主键。

        返回结果：
            非负整数。

        异常说明：
            无。

        业务规则：
            ACTIVE 且未删除的关系计入。
        """

        return int(
            self.session.scalar(
                select(func.count()).select_from(PartyParkRelation).where(
                    PartyParkRelation.tenant_id == self.ctx.tenant_id,
                    PartyParkRelation.party_role_id == party_role_id,
                    PartyParkRelation.status == "ACTIVE",
                    PartyParkRelation.deleted_at.is_(None),
                )
            )
            or 0
        )

    def add(self, model: PartyRole) -> PartyRole:
        """功能说明：
            插入角色并 flush。

        业务职责：
            写入；强制 tenant_id。

        输入参数：
            model：PartyRole。

        返回结果：
            flush 后的 model。

        异常说明：
            IntegrityError 由上层处理。

        业务规则：
            tenant_id = ctx.tenant_id。
        """

        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: PartyRole) -> PartyRole:
        """功能说明：
            保存角色变更并 flush。

        业务职责：
            更新。

        输入参数：
            model：PartyRole。

        返回结果：
            flush 后的 model。

        异常说明：
            无。

        业务规则：
            无额外校验。
        """

        self.session.add(model)
        self.session.flush()
        return model


class PartyParkRelationRepository:
    """功能说明：
        Party–Park 关系仓储（租户强制）。

    业务职责：
        Infrastructure；关系列表与 ACTIVE 查找。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_party(self, party_id: int) -> list[PartyParkRelation]:
        """功能说明：
            列出主体未软删的园区关系。

        业务职责：
            查询。

        输入参数：
            party_id：主体 ID。

        返回结果：
            PartyParkRelation 列表。

        异常说明：
            无。

        业务规则：
            deleted_at 为空；含 ENDED。
        """

        return list(
            self.session.scalars(
                select(PartyParkRelation)
                .where(
                    PartyParkRelation.tenant_id == self.ctx.tenant_id,
                    PartyParkRelation.party_id == party_id,
                    PartyParkRelation.deleted_at.is_(None),
                )
                .order_by(PartyParkRelation.id)
            ).all()
        )

    def get(self, relation_id: int, party_id: int) -> Optional[PartyParkRelation]:
        """功能说明：
            按关系 ID + 主体 ID 加载关系。

        业务职责：
            归属校验。

        输入参数：
            relation_id：关系主键。
            party_id：必须匹配的主体。

        返回结果：
            PartyParkRelation 或 None。

        异常说明：
            无。

        业务规则：
            跨主体返回 None；已软删返回 None。
        """

        return self.session.scalars(
            select(PartyParkRelation).where(
                PartyParkRelation.tenant_id == self.ctx.tenant_id,
                PartyParkRelation.party_id == party_id,
                PartyParkRelation.id == relation_id,
                PartyParkRelation.deleted_at.is_(None),
            )
        ).first()

    def find_active(
        self, party_id: int, park_id: int, party_role_id: int
    ) -> Optional[PartyParkRelation]:
        """功能说明：
            查找三元组唯一 ACTIVE 关系。

        业务职责：
            重复创建预检。

        输入参数：
            party_id/park_id/party_role_id：关系三元组。

        返回结果：
            已存在的 ACTIVE 关系或 None。

        异常说明：
            无。

        业务规则：
            与部分唯一索引语义对齐。
        """

        return self.session.scalars(
            select(PartyParkRelation).where(
                PartyParkRelation.tenant_id == self.ctx.tenant_id,
                PartyParkRelation.party_id == party_id,
                PartyParkRelation.park_id == park_id,
                PartyParkRelation.party_role_id == party_role_id,
                PartyParkRelation.status == "ACTIVE",
                PartyParkRelation.deleted_at.is_(None),
            )
        ).first()

    def add(self, model: PartyParkRelation) -> PartyParkRelation:
        """功能说明：
            插入园区关系并 flush。

        业务职责：
            写入；强制 tenant_id。

        输入参数：
            model：PartyParkRelation。

        返回结果：
            flush 后的 model。

        异常说明：
            IntegrityError 由上层映射 DUPLICATE。

        业务规则：
            tenant_id = ctx.tenant_id。
        """

        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: PartyParkRelation) -> PartyParkRelation:
        """功能说明：
            保存关系变更并 flush。

        业务职责：
            更新（如结束关系）。

        输入参数：
            model：PartyParkRelation。

        返回结果：
            flush 后的 model。

        异常说明：
            无。

        业务规则：
            无。
        """

        self.session.add(model)
        self.session.flush()
        return model


class PartyContactRepository:
    """功能说明：
        联系人仓储（软删过滤 + 租户强制）。

    业务职责：
        Infrastructure；联系人 CRUD 持久化。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_party(self, party_id: int) -> list[PartyContact]:
        """功能说明：
            列出主体未删除联系人。

        业务职责：
            查询。

        输入参数：
            party_id：主体 ID。

        返回结果：
            PartyContact 列表。

        异常说明：
            无。

        业务规则：
            is_deleted=False；租户强制。
        """

        return list(
            self.session.scalars(
                select(PartyContact)
                .where(
                    PartyContact.tenant_id == self.ctx.tenant_id,
                    PartyContact.party_id == party_id,
                    PartyContact.is_deleted.is_(False),
                )
                .order_by(PartyContact.id)
            ).all()
        )

    def get(self, contact_id: int, party_id: int) -> Optional[PartyContact]:
        """功能说明：
            按联系人 ID + 主体 ID 加载。

        业务职责：
            归属校验。

        输入参数：
            contact_id：联系人主键。
            party_id：必须匹配的主体。

        返回结果：
            PartyContact 或 None。

        异常说明：
            无。

        业务规则：
            已软删返回 None。
        """

        return self.session.scalars(
            select(PartyContact).where(
                PartyContact.tenant_id == self.ctx.tenant_id,
                PartyContact.party_id == party_id,
                PartyContact.id == contact_id,
                PartyContact.is_deleted.is_(False),
            )
        ).first()

    def clear_primary(self, party_id: int) -> None:
        """功能说明：
            清除主体下所有主联系人标记。

        业务职责：
            设置新 primary 前的互斥。

        输入参数：
            party_id：主体 ID。

        返回结果：
            None。

        异常说明：
            无。

        业务规则：
            仅未删除联系人。
        """

        for c in self.list_for_party(party_id):
            if c.is_primary:
                c.is_primary = False
                self.session.add(c)
        self.session.flush()

    def add(self, model: PartyContact) -> PartyContact:
        """功能说明：
            插入联系人并 flush。

        业务职责：
            写入；强制 tenant_id。

        输入参数：
            model：PartyContact。

        返回结果：
            flush 后的 model。

        异常说明：
            无。

        业务规则：
            tenant_id = ctx.tenant_id。
        """

        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: PartyContact) -> PartyContact:
        """功能说明：
            保存联系人变更并 flush。

        业务职责：
            更新/软删。

        输入参数：
            model：PartyContact。

        返回结果：
            flush 后的 model。

        异常说明：
            无。

        业务规则：
            无。
        """

        self.session.add(model)
        self.session.flush()
        return model


class PartyAddressRepository:
    """功能说明：
        地址仓储。PERSON 访问拒绝由 Application 强制，本层仅持久化。

    业务职责：
        Infrastructure；租户 + party 归属过滤；不判定 party_type。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_party(self, party_id: int) -> list[PartyAddress]:
        """功能说明：
            列出主体未软删地址行。

        业务职责：
            查询；调用方须先完成 PERSON 拒绝。

        输入参数：
            party_id：主体 ID。

        返回结果：
            PartyAddress 列表。

        异常说明：
            无。

        业务规则：
            tenant_id 强制；deleted_at 为空。
        """

        return list(
            self.session.scalars(
                select(PartyAddress)
                .where(
                    PartyAddress.tenant_id == self.ctx.tenant_id,
                    PartyAddress.party_id == party_id,
                    PartyAddress.deleted_at.is_(None),
                )
                .order_by(PartyAddress.id)
            ).all()
        )

    def get(self, address_id: int, party_id: int) -> Optional[PartyAddress]:
        """功能说明：
            按地址 ID + 主体 ID 加载。

        业务职责：
            归属校验查询。

        输入参数：
            address_id：地址主键。
            party_id：必须匹配的主体。

        返回结果：
            PartyAddress 或 None。

        异常说明：
            无。

        业务规则：
            跨主体/跨租户/已软删返回 None。
        """

        return self.session.scalars(
            select(PartyAddress).where(
                PartyAddress.tenant_id == self.ctx.tenant_id,
                PartyAddress.party_id == party_id,
                PartyAddress.id == address_id,
                PartyAddress.deleted_at.is_(None),
            )
        ).first()

    def clear_primary(self, party_id: int, address_type: str) -> None:
        """功能说明：
            清除指定类型下的 primary 标记。

        业务职责：
            设置新 primary 前的互斥。

        输入参数：
            party_id：主体 ID。
            address_type：地址类型枚举。

        返回结果：
            None。

        异常说明：
            无。

        业务规则：
            仅同 address_type。
        """

        for a in self.list_for_party(party_id):
            if a.address_type == address_type and a.is_primary:
                a.is_primary = False
                self.session.add(a)
        self.session.flush()

    def add(self, model: PartyAddress) -> PartyAddress:
        """功能说明：
            插入地址并 flush。

        业务职责：
            写入；强制 tenant_id。

        输入参数：
            model：PartyAddress。

        返回结果：
            flush 后的 model。

        异常说明：
            IntegrityError（primary 冲突）由上层映射。

        业务规则：
            不在此层拒绝 PERSON。
        """

        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model: PartyAddress) -> PartyAddress:
        """功能说明：
            保存地址变更并 flush。

        业务职责：
            更新/软删。

        输入参数：
            model：PartyAddress。

        返回结果：
            flush 后的 model。

        异常说明：
            IntegrityError 由上层映射。

        业务规则：
            无。
        """

        self.session.add(model)
        self.session.flush()
        return model


class PartyRiskEventRepository:
    """功能说明：
        风险事件只追加仓储（无更新/删除）。

    业务职责：
        Infrastructure；保证事件不可变写入路径。
    """

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    def list_for_party(self, party_id: int) -> list[PartyRiskEvent]:
        """功能说明：
            按时间倒序列出主体风险事件。

        业务职责：
            查询；读权限由 Application 校验。

        输入参数：
            party_id：主体 ID。

        返回结果：
            PartyRiskEvent 列表（id 降序）。

        异常说明：
            无。

        业务规则：
            租户强制。
        """

        return list(
            self.session.scalars(
                select(PartyRiskEvent)
                .where(
                    PartyRiskEvent.tenant_id == self.ctx.tenant_id,
                    PartyRiskEvent.party_id == party_id,
                )
                .order_by(PartyRiskEvent.id.desc())
            ).all()
        )

    def add(self, model: PartyRiskEvent) -> PartyRiskEvent:
        """功能说明：
            追加风险事件并 flush。

        业务职责：
            只写新增；无 update/delete API。

        输入参数：
            model：PartyRiskEvent。

        返回结果：
            flush 后的 model。

        异常说明：
            无。

        业务规则：
            tenant_id = ctx.tenant_id；事件不可变。
        """

        model.tenant_id = self.ctx.tenant_id
        self.session.add(model)
        self.session.flush()
        return model
