"""Seed minimal tenant for step1.

功能说明：
    本地/测试环境幂等种子默认租户、权限字典、ADMIN 角色与管理员用户。

业务职责：
    infrastructure/bootstrap 边界内允许直接使用 ORM；
    禁止固定明文密码；生产环境禁止自动种子。
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.infrastructure.database.models.identity import (
    Menu,
    Permission,
    Role,
    RoleMenu,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from app.infrastructure.database.models.organization_governance import FieldAccessPolicy

logger = logging.getLogger(__name__)

DEFAULT_PERMISSIONS = (
    ("*", "全部权限", "system"),
    ("park:read", "查看园区", "park"),
    ("park:write", "维护园区", "park"),
    ("unit:read", "查看单元", "unit"),
    ("unit:write", "维护单元", "unit"),
    ("party:read", "查看主体", "party"),
    ("party:write", "维护主体", "party"),
    ("party:manage_unscoped", "管理未关联园区主体", "party"),
    ("party:risk_read", "查看主体风险历史", "party"),
    ("party:risk_manage", "管理主体黑名单", "party"),
    ("party:credential_read", "查看企业证照", "party"),
    ("party:credential_manage", "管理企业证照", "party"),
    ("lease:read", "查看租赁合同", "lease"),
    ("lease:write", "维护租赁合同", "lease"),
    ("lease:activate", "提交/激活租赁合同", "lease"),
    ("lease:terminate", "终止租赁合同", "lease"),
    ("lease:change", "发起合同变更", "lease"),
    ("lease:approve", "审批合同业务", "lease"),
    ("lease:approve_override", "越权审批合同业务", "lease"),
    ("lease:document", "管理合同文档", "lease"),
    ("lease:settle", "管理退租结算", "lease"),
    ("lease:finance_clearance", "确认退租财务清算证据", "lease"),
    ("bill:read", "查看账单", "billing"),
    ("bill:write", "维护账单草稿", "billing"),
    ("bill:issue", "签发/作废账单", "billing"),
    ("payment:read", "查看收款登记", "collection"),
    ("payment:write", "登记收款与核销", "collection"),
    ("work_item:read", "查看工作台待办", "workbench"),
    ("work_item:write", "维护工作台待办", "workbench"),
    ("work_item:reassign", "改派工作台待办", "workbench"),
    ("work_item:override_source", "覆盖来源待办状态", "workbench"),
    ("workbench.layout.read", "查看工作台布局", "workbench"),
    ("workbench.layout.write", "维护个人工作台布局", "workbench"),
    ("workbench.layout.admin", "维护角色工作台布局", "workbench"),
    ("notification.read", "查看站内通知", "workbench"),
    ("notification.write", "处理站内通知", "workbench"),
    ("automation.rule.read", "查看自动化规则与执行", "workbench"),
    ("automation.rule.write", "维护自动化规则", "workbench"),
    ("scheduler.read", "查看调度定义与运行", "workbench"),
    ("scheduler.write", "维护调度定义", "workbench"),
    ("scheduler.run", "执行与恢复调度", "workbench"),
    ("event.read", "查看业务事件与消费状态", "workbench"),
    ("event.emit", "提交已注册业务事件", "workbench"),
    ("event.dispatch", "派发业务事件", "workbench"),
    ("event.replay", "重放死信事件", "workbench"),
    ("asset.template.read", "查看资产业态模板", "park_property"),
    ("asset.template.write", "维护资产业态模板", "park_property"),
    ("lead.assignment_rule.read", "查看招商自动分配规则", "investment"),
    ("lead.assignment_rule.write", "维护招商自动分配规则", "investment"),
    ("lead.assignment_rule.run", "执行招商自动分配", "investment"),
    ("lead.viewing.read", "查看招商带看", "investment"),
    ("lead.viewing.write", "维护招商带看", "investment"),
    ("lead.intent.read", "查看招商意向", "investment"),
    ("lead.intent.write", "维护招商意向", "investment"),
    ("lead.intent.submit", "提交招商意向审批", "investment"),
    ("lead.channel.read", "查看招商渠道", "investment"),
    ("lead.channel.write", "维护招商渠道", "investment"),
    ("lead.channel.replay", "重放招商渠道事件", "investment"),
    ("lead:read", "查看招商线索", "investment"),
    ("lead:write", "维护招商线索", "investment"),
    ("lead:convert", "转化招商线索", "investment"),
    ("lead:claim", "领取公海线索", "investment"),
    ("lead:manage", "分配合并招商线索", "investment"),
    ("lead:lock", "匹配与锁定出租单元", "investment"),
    ("work_order:read", "查看运维工单", "facility_ops"),
    ("work_order:write", "维护运维工单", "facility_ops"),
    ("collection:read", "查看催缴案件", "collection"),
    ("collection:write", "维护催缴案件", "collection"),
    ("approval:read", "查看审批", "workflow"),
    ("approval:write", "提交审批", "workflow"),
    ("approval:decide", "审批决定", "workflow"),
    ("approval.definition.read", "查看审批定义", "workflow"),
    ("approval.definition.write", "维护审批定义", "workflow"),
    ("approval.task.read", "查看审批任务", "workflow"),
    ("approval.task.decide", "处理审批任务", "workflow"),
    ("approval.task.override_self", "越权自审批", "workflow"),
    ("approval.delegation.manage", "管理审批委托", "workflow"),
    ("audit.read", "查看审计中心", "audit"),
    ("audit.export", "导出审计记录", "audit"),
    ("attachment:read", "查看附件", "attachment"),
    ("attachment:write", "上传删除附件", "attachment"),
    ("identity.user.read", "查看用户", "identity"),
    ("identity.user.write", "维护用户", "identity"),
    ("identity.role.read", "查看角色", "identity"),
    ("identity.role.write", "维护角色", "identity"),
    ("identity.menu.read", "查看菜单", "identity"),
    ("identity.menu.write", "维护菜单", "identity"),
    ("identity.org.read", "查看组织", "identity"),
    ("identity.org.write", "维护组织", "identity"),
    ("identity.dict.read", "查看字典", "identity"),
    ("identity.dict.write", "维护字典", "identity"),
    ("identity.param.read", "查看系统参数", "identity"),
    ("identity.param.write", "维护系统参数", "identity"),
    ("identity.org_governance.read", "查看组织治理", "identity"),
    ("identity.org_governance.write", "维护组织治理", "identity"),
    ("identity.field_policy.read", "查看字段策略", "identity"),
    ("identity.field_policy.write", "维护字段策略", "identity"),
)


def ensure_default_tenant(session: Session) -> Tenant | None:
    """幂等创建本地默认租户、管理员及显式超级权限关系。

    规则：
    - production：禁止调用（抛错）。
    - admin 已存在：不重置密码。
    - admin 不存在：仅当 LOCAL_ADMIN_PASSWORD 非空时创建哈希。
    - ADMIN 角色：动作权限 `*` + all_parks=True（园区范围与动作正交）。
    """

    settings = get_settings()
    env = settings.app_env.lower()
    if env == "production":
        raise RuntimeError("production 禁止 ensure_default_tenant 自动种子")

    tenant = session.scalars(select(Tenant).where(Tenant.code == "default")).first()
    if tenant is None:
        tenant = Tenant(
            code="default",
            name="默认租户",
            status="ACTIVE",
            db_strategy="SHARED",
        )
        session.add(tenant)
        session.flush()

    permissions: dict[str, Permission] = {}
    for code, name, module in DEFAULT_PERMISSIONS:
        permission = session.scalars(select(Permission).where(Permission.code == code)).first()
        if permission is None:
            permission = Permission(code=code, name=name, module=module)
            session.add(permission)
            session.flush()
        permissions[code] = permission

    role = session.scalars(
        select(Role).where(Role.tenant_id == tenant.id, Role.code == "ADMIN")
    ).first()
    if role is None:
        role = Role(
            tenant_id=tenant.id,
            code="ADMIN",
            name="系统管理员",
            status="ACTIVE",
            remark="本地 Step1 默认管理员角色",
            all_parks=True,
        )
        session.add(role)
        session.flush()
    elif not bool(role.all_parks):
        # 兼容旧库：ADMIN 历史依赖 * 兼全园，回填显式 all_parks
        role.all_parks = True
        session.add(role)
        session.flush()

    star = permissions["*"]
    role_permission = session.scalars(
        select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == star.id,
        )
    ).first()
    if role_permission is None:
        session.add(
            RolePermission(
                tenant_id=tenant.id,
                role_id=role.id,
                permission_id=star.id,
            )
        )

    # 本地 ADMIN 的手机号查看是显式数据库策略；`*` 动作权限本身不绕过字段门禁。
    admin_phone_policy = session.scalars(
        select(FieldAccessPolicy).where(
            FieldAccessPolicy.tenant_id == tenant.id,
            FieldAccessPolicy.role_id == role.id,
            FieldAccessPolicy.resource_type == "USER",
            FieldAccessPolicy.field_name == "phone",
        )
    ).first()
    if admin_phone_policy is None:
        session.add(
            FieldAccessPolicy(
                tenant_id=tenant.id,
                role_id=role.id,
                resource_type="USER",
                field_name="phone",
                access_mode="VISIBLE",
                mask_strategy="PHONE",
                status="ACTIVE",
            )
        )

    user = session.scalars(
        select(User).where(User.tenant_id == tenant.id, User.username == "admin")
    ).first()
    if user is None:
        password = (settings.local_admin_password or "").strip()
        if not password:
            msg = (
                "LOCAL_ADMIN_PASSWORD 未设置，跳过创建默认 admin 用户；"
                "本地首次启动请在环境变量中提供密码后重启。"
            )
            logger.error(msg)
            if settings.local_admin_password_required:
                session.rollback()
                raise RuntimeError(msg)
            session.commit()
            session.refresh(tenant)
            return tenant

        user = User(
            tenant_id=tenant.id,
            username="admin",
            password_hash=hash_password(password),
            real_name="管理员",
            status="ACTIVE",
            all_parks=False,  # 园区范围来自 ADMIN 角色 all_parks
        )
        session.add(user)
        session.flush()
    # 已存在 admin：幂等跳过，绝不重置 password_hash

    user_role = session.scalars(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    ).first()
    if user_role is None:
        session.add(UserRole(tenant_id=tenant.id, user_id=user.id, role_id=role.id))

    # 默认导航菜单（幂等按 path）
    dashboard = session.scalars(
        select(Menu).where(Menu.tenant_id == tenant.id, Menu.path == "/dashboard")
    ).first()
    if dashboard is None:
        dashboard = Menu(
            tenant_id=tenant.id,
            name="工作台",
            path="/dashboard",
            component="Dashboard",
            sort_order=1,
            menu_type="MENU",
            status="ACTIVE",
        )
        session.add(dashboard)
        session.flush()
    system = session.scalars(
        select(Menu).where(Menu.tenant_id == tenant.id, Menu.path == "/system")
    ).first()
    if system is None:
        system = Menu(
            tenant_id=tenant.id,
            name="系统管理",
            path="/system",
            component="Layout",
            sort_order=90,
            menu_type="DIR",
            status="ACTIVE",
        )
        session.add(system)
        session.flush()
        session.add(
            Menu(
                tenant_id=tenant.id,
                parent_id=system.id,
                name="用户管理",
                path="/system/users",
                component="system/Users",
                sort_order=1,
                menu_type="MENU",
                status="ACTIVE",
                permission_code="identity.user.read",
            )
        )
        session.add(
            Menu(
                tenant_id=tenant.id,
                parent_id=system.id,
                name="角色管理",
                path="/system/roles",
                component="system/Roles",
                sort_order=2,
                menu_type="MENU",
                status="ACTIVE",
                permission_code="identity.role.read",
            )
        )

    # ADMIN 角色绑定全部菜单
    all_menus = list(session.scalars(select(Menu).where(Menu.tenant_id == tenant.id)).all())
    for menu in all_menus:
        link = session.scalars(
            select(RoleMenu).where(RoleMenu.role_id == role.id, RoleMenu.menu_id == menu.id)
        ).first()
        if link is None:
            session.add(RoleMenu(tenant_id=tenant.id, role_id=role.id, menu_id=menu.id))

    session.commit()
    session.refresh(tenant)
    return tenant
