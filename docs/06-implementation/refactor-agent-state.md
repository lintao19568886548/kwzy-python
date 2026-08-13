# KWZY Python 自治重构状态

| 字段 | 值 |
| --- | --- |
| 更新时间 | 2026-08-13 |
| 当前分支 | `feat/park-workbench-todos` |
| 基线 main | Identity 已 merge（`030a05a`） |
| 当前阶段 | Workbench 待办（WorkItem）实现 |
| 当前领域 | workbench / work_items |
| Alembic head | `c9a57b2d0f31`（revises `b8f46a1c9e20`） |
| 部署 | **未部署** |
| 生产迁移 | **NOT_EXECUTED** |
| 允许合并 main | Workbench 回归通过后可评估 merge；全系统 COMPLETE 仍未达 |

## 本迭代完成

- `WorkItem` ORM + Alembic `c9a57b2d0f31`
- Repository / Application / REST：`/work-items` list·create·get·complete·cancel·reopen
- 权限：`work_item:read` / `work_item:write`（bootstrap 种子）
- `ensure_from_source` 来源幂等（供账单/合同事件后续挂接）
- OpenAPI 契约路径 + pytest

## 已确认基线

- Party / Lease / Bill / Payment / Identity 已在 main
- 旧 Java 根：`D:\重构python\kwzg-Java-main`（只读）
- origin：`https://github.com/lintao19568886548/kwzy-python.git`

## 下一步

1. 事件驱动自动开待办（合同到期、账单未结）挂接 ensure_from_source
2. Analytics workbench 聚合真实 todos 计数
3. FE 工作台页
4. 招商/工单等领域推进
5. 全量代码验收前禁止 KWZY_*_COMPLETE

## 永久门禁

- 无 force push / reset --hard
- 无生产 DB / 真实密钥
- 无 STUB 冒充 COMPLETE
