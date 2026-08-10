## Why

`design-party-domain` 已批准归档。`implement-party-master` 规划结构通过，但 **apply 暂不批准**。须先关闭门禁：PostgreSQL 16 测试环境可验证、地址独立表、`feat/party-master` 分支门禁、OpenAPI 主档去 `park_id` 契约同步。本修订只更新规划与设计草案，不 apply、不编码。

## What Changes

**规划/设计修订 only：**

- 固定 PG 16 测试首选方案（Docker Compose 一次性测试库）+ apply 前连接验证门禁  
- Party 地址改为 **`party_addresses` 独立表**（ADR-003g）；主档不再用模糊 `address` 作事实来源  
- tasks 明确 **apply 前** 创建 `feat/party-master`（本阶段不创建分支）  
- 旧 OpenAPI `Party.park_id`：新契约移除；可选 `initial_park_relation` 组合命令；契约测试防回退  
- 任务拆分含 PG 门禁、地址 API、OpenAPI 兼容检查  

**禁止本阶段：** apply、业务代码、正式 Alembic、改库、启容器、建分支、提交推送。

**明确不包含实现：** Lease/Bill/Payment、证件、旧库 ETL、`/rental/tenant` 适配器、前端。

## Capabilities

### New Capabilities

- `party-master-delivery`: 模块布局、分层、分支门禁、完成报告  
- `party-migration-ops`: Alembic/PG16/备份  
- `party-test-matrix`: SQLite 快测 + PG 集成门禁  
- `party-addresses`: 独立地址表与 API、PERSON 隐私边界  
- `party-openapi-contract`: 主档无 park_id、initial_park_relation、契约测试  

### Modified Capabilities

- （相对前一版规划）地址从主档字段改为独立表；OpenAPI park_id 契约强制修订  

## Impact

| 面 | 说明 |
| --- | --- |
| 设计文档 | DDL/API/ADR/实施计划同步 `party_addresses` |
| apply | **阻塞**至 PG 环境实际可连且门禁任务完成 |
| 代码/库 | 本阶段无变更 |
