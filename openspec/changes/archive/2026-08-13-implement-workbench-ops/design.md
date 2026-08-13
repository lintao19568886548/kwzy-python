# Design: workbench ops

## Context

WorkItem 表已存在唯一键 `(tenant_id, source_type, source_id, item_type)`。  
账单侧已用 `BILL` + `BILL_UNPAID`。合同侧使用 `LEASE` + `CONTRACT_EXPIRING`。

## Decisions

1. WorkItem 不拥有合同/账单状态；仅镜像运营任务。
2. 领域服务通过 `ensure_from_source` / `cancel_by_source` 同事务 flush（commit=False）。
3. Summary 只读聚合：open/overdue/due_soon todos + unpaid bills + expiring contracts。
4. 定时扫描以显式 job API 提供，部署侧用 cron 调用（本阶段不引入分布式调度器）。

## Permissions

- `work_item:read`：列表/详情/summary
- `work_item:write`：创建/完成/取消/reopen/sync job

## Risks

- 大量合同扫描性能：limit 500，后续批处理
- 跨模块应用依赖：允许模块化单体内应用编排
