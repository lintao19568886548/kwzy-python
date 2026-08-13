# KWZY Python 自治重构状态

| 字段 | 值 |
| --- | --- |
| 更新时间 | 2026-08-13 |
| 当前分支 | `main` |
| main HEAD | 含 workbench merge + bill 待办挂接 |
| 当前阶段 | Workbench 待办 + 账单事件闭环 |
| 当前领域 | workbench / billing 联动 |
| Alembic head | `c9a57b2d0f31`（revises `b8f46a1c9e20`） |
| 部署 | **未部署** |
| 生产迁移 | **NOT_EXECUTED** |
| 全系统 COMPLETE | **未达** |

## 本迭代完成

- `WorkItem` ORM + Alembic `c9a57b2d0f31`（已 merge main）
- REST：`/work-items` list·create·get·complete·cancel·reopen
- 权限：`work_item:read` / `work_item:write`
- `ensure_from_source` / `complete_by_source` / `cancel_by_source`（commit 可选）
- 账单：issue 开待办、PAID 完成、冲正复开、void 取消
- OpenAPI + pytest

## 已确认基线

- Party / Lease / Bill / Payment / Identity / Workbench 已在 main
- 旧 Java 根：`D:\重构python\kwzg-Java-main`（只读）
- origin：`https://github.com/lintao19568886548/kwzy-python.git`

## 下一步

1. 合同到期自动待办
2. Analytics workbench 聚合真实 todos 计数
3. FE 工作台页
4. 招商/工单等领域推进
5. 全量代码验收前禁止 KWZY_*_COMPLETE

## 永久门禁

- 无 force push / reset --hard
- 无生产 DB / 真实密钥
- 无 STUB 冒充 COMPLETE
