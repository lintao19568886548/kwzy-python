# 业务蓝图需求追踪矩阵（v1 启动版）

> 持续填充。状态：IN_PROGRESS。目标：`DOC_REQUIREMENTS_UNTRACKED=0`。

| requirement_id | source_document | original_goal | user_role | domain | implementation_status | acceptance_status | priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BP-AUTH-001 | 01-old-system-analysis/02-backend | 用户名密码登录+租户识别 | 全员 | identity | PARTIAL（login 已有） | IN_PROGRESS | MUST |
| BP-AUTH-002 | 01-old-system-analysis/02-backend | Refresh/Logout 会话 | 全员 | identity | MISSING | PENDING | MUST |
| BP-AUTH-003 | 01-old-system-analysis/02-backend | 修改密码/会话失效 | 全员/管理员 | identity | MISSING | PENDING | MUST |
| BP-AUTH-004 | 01-old-system-analysis/02-backend | 权限码列表 | 全员 | identity | PARTIAL（JWT claims） | PENDING | MUST |
| BP-RBAC-001 | 01-old-system-analysis/02-backend | 用户生命周期 | 管理员 | identity | MISSING | PENDING | MUST |
| BP-RBAC-002 | 01-old-system-analysis/02-backend | 角色与权限绑定 | 管理员 | identity | PARTIAL（模型已有） | PENDING | MUST |
| BP-RBAC-003 | 01-old-system-analysis/02-backend | 动态菜单 | 全员 | identity | MISSING | PENDING | MUST |
| BP-RBAC-004 | 01-old-system-analysis/02-backend | 园区数据范围 | 管理员 | identity | PARTIAL | IN_PROGRESS | MUST |
| BP-PARTY-001 | phase06-party | 主体主数据 | 招商/财务 | party | COMPLETE | PASS | MUST |
| BP-LEASE-001 | phase06-lease | 合同与占用 | 招商/园区 | lease | COMPLETE | PASS | MUST |
| BP-BILL-001 | phase06-bill | 账单制单/作废 | 财务 | billing | COMPLETE | PASS | MUST |
| BP-PAY-001 | phase06-payment | 收款登记/核销 | 出纳 | collection | COMPLETE | PASS | MUST |
| BP-PARK-001 | 01-old-system-analysis | 园区/房源 | 园区经理 | park | PARTIAL | PENDING | MUST |
| BP-INV-001 | 01-old-system-analysis | 招商线索 | 招商 | investment | STUB | PENDING | SHOULD |
| BP-OPS-001 | 01-old-system-analysis | 运维工单 | 工程 | tenant_ops | STUB | PENDING | SHOULD |
| BP-AI-001 | 01-old-system-analysis | AI 辅助 | 多角色 | ai_assist | STUB | PENDING | INNOVATION |
| BP-DASH-001 | 01-old-system-analysis | 经营看板 | 老板/总经理 | analytics | STUB | PENDING | SHOULD |
| BP-TODO-001 | 01-old-system-analysis/06 | 自动待办闭环 | 多角色 | platform | MISSING | PENDING | INNOVATION |
| BP-ETL-001 | 03-database | 旧数据迁移工具 | 运维 | platform | MISSING | BLOCKED_FIELD_MAP | MUST |

## 统计（启动）

| 状态 | 数量 |
| --- | ---: |
| COMPLETE | 4 |
| PARTIAL | 4 |
| STUB | 4 |
| MISSING | 6 |
| UNTRACKED | 0（本表覆盖启动集合；后续 docs 全量扫描继续追加） |
