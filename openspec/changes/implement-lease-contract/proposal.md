# Change: implement-lease-contract

## Why

Party 主数据已交付（`feat/party-master`@`d7e1300`）。阶段 06 核心路径要求打通 **ParkProperty → Lease → Billing → Collection**。本 change 仅实现 **租赁合同（Lease Contract）** 限界上下文的主数据与生命周期，不实现账单出账与收款核销。

依据：

- `docs/02-domain-design/01-domain-overview.md`
- `docs/02-domain-design/02-aggregates-and-state-machines.md` §2 Lease
- `docs/02-domain-design/05-phase06-scope.md`（Lease in scope）
- `docs/03-database/01-core-ddl-v1.sql` lease_* 表草案
- 工程规范 `docs/07-engineering-standard/*`

## What Changes

- 实现 `lease_contracts` / `lease_contract_units` / `lease_terms`（Alembic 新 revision，PostgreSQL 16 权威）
- DDD 分层：Domain / Application / Infrastructure / Interface
- 合同生命周期：DRAFT → PENDING_ACTIVE → ACTIVE；cancel；activate；terminate；breached（按已批准状态机）
- 占用：合同单元行 + activate 时占用冲突检测；Unit.used_area 投影回写
- 权限、tenant 隔离、park scope、审计与日志
- OpenAPI 与测试矩阵

## Out of Scope（本 change 禁止）

- Bill / Payment / Allocation / 出账计算 / 滞纳金 / 税费舍入
- 押金台账与退租财务结算（`deposit_amount` 仅存字段，不实现退款流水）
- 附件对象存储上传实现（可预留 resource 元数据接口或延后）
- 旧 Java `rental_tenant` 适配器与 ETL
- 自动 EXPIRING 定时任务的产品化调度（可提供标记规则与可测服务方法，默认 N 天须文档化）
- 合并 main / 部署生产

## Impact

- 新 feature 分支：`feat/lease-contract`（parent：`feat/party-master`）
- 依赖已存在：Party、Park、Unit、Identity
- 既有 `app/modules/lease/api.py` stub 将被正式实现替换（不挂载冲突路由）
