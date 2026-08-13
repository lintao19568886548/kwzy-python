# Change: implement-investment-leads

## Why

招商线索是增长主链入口；当前 `/leads` 为 stub，无法支撑真实业务与前端。

## What Changes

- `leads` 表与 Alembic `d0b68c3e1a42`
- Lead 状态机 NEW/FOLLOWING/WON/LOST/CANCELLED
- API：list/create/get/update/lose/convert
- 转化：创建 Party（LESSEE 园区关系）+ 可选 Lease DRAFT
- 跟进待办 `LEAD_FOLLOW` 与 workbench 联动
- 权限 `lead:read|write|convert`
- OpenAPI + 前端招商页 + pytest

## Impact

- investment 模块去 stub
- 不实现雷达爬虫/企微 CRM（DEFER）

## Strategy

REDESIGN：线索独立聚合，转化编排 Party/Lease，不侵入其状态机。
