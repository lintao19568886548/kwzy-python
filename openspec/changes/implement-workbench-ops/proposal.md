# Change: implement-workbench-ops

## Why

运营工作台与自动待办是园区日常驾驶舱能力；已有 WorkItem 基础与账单挂接，需补齐合同到期、聚合指标与同步作业。

## What Changes

- 合同激活/终止与 `CONTRACT_EXPIRING` 待办联动
- `GET /workbench/summary` 运营指标
- `POST /workbench/jobs/sync-lease-todos` 幂等扫描
- OpenAPI + 测试

## Impact

- Affected: workbench, lease, billing metrics read
- Non-goals: 侵入 Lease/Bill 状态机；完整催缴案件；前端全量

## Strategy

REDESIGN / INNOVATION：任务生命周期独立于领域聚合。
