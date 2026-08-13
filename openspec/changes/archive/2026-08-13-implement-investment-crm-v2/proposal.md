## Why

现有招商能力只有单表 Lead CRUD、简单状态更新和转 Party/合同草稿，既不能治理旧系统 `investment` 与 radar lead 双轨造成的重复客户，也没有公海分配、独立跟进时间线、可验证房源锁定、原子转化和一致漏斗口径。资产与租控纵切已经提供 current-only 出租单元和并发基础，现在应先建立不依赖外部爬虫、企微或 AI 的核心 CRM 闭环，再承接渠道与智能能力。

## What Changes

- **BREAKING**：将线索阶段统一为 `NEW → CONTACTING → VISITING → QUOTING → NEGOTIATING → WON/LOST/CANCELLED/MERGED`；旧 `FOLLOWING` 写入在兼容期映射为 `CONTACTING`，存量数据迁移到新阶段。
- 增加规范化电话/名称的重复候选检查、带理由的重复覆盖和保留完整血缘的线索合并，禁止静默产生重复主档。
- 增加私有/公海池、分配/领取/释放/超时回收、负责人范围可见性和不可抵赖的分配历史；所有动作受租户、园区和权限约束。
- 增加 append-only 跟进活动、下一次跟进、阶段推进、逾期待办和完整时间线，避免用覆盖 remark 冒充销售过程。
- 增加基于 current VACANT 单元的可解释规则匹配，以及带到期时间的排他锁房；PostgreSQL 并发下同一单元只能有一个有效锁。
- 修复 Lead→Party→可选 Lease DRAFT 的跨服务多次提交，使转化、锁房消费、审计和待办关闭在一个事务中成功或回滚。
- 增加按园区/来源/负责人/阶段/时间过滤的一致漏斗与公海指标，以及新的 PC 招商工作台、详情时间线、匹配/锁房和权限/异常状态。
- 发布旧 `investment`/CRM/radar lead 的接口处置与字段映射，并提供独立 PostgreSQL 合成 ETL 的 dry-run、首次导入、幂等重放、对账和回滚；真实旧数据与外部渠道继续受人工授权门禁。

## Capabilities

### New Capabilities

- `lead-deduplication`: 规范化重复候选、覆盖理由、合并不变量和血缘查询。
- `lead-assignment-pool`: 私有/公海、分配/领取/释放/回收、可见范围和并发所有权。
- `lead-activity-pipeline`: 销售阶段机、append-only 跟进活动、下一跟进与逾期待办。
- `unit-opportunity-locking`: 可解释房源匹配、限时排他锁、过期/释放/转化和出租单元状态投影。
- `investment-funnel-query`: 统一过滤条件下的阶段、来源、负责人和时效漏斗指标。
- `investment-crm-pc`: 园区选择、看板/列表、公海、详情时间线、分配、匹配、锁房和全状态 PC 体验。
- `investment-crm-data-migration`: 旧招商双轨处置、字段映射、合成导入幂等/对账/回滚与真实数据门禁。

### Modified Capabilities

- `investment-leads`: 扩展基础 Lead 生命周期、数据范围、转化原子性和兼容阶段语义。

## Impact

- 数据库：扩展 `leads`，新增活动、分配历史、合并血缘和单元锁表；新增单一 Alembic head 迁移并保留现有外键。
- 后端：重构 investment 聚合、仓储和服务，调整 Party/Lease 服务的可组合事务边界，新增 CRM 查询和锁房 API/权限/审计。
- 前端：替换 `/leads` 的手填 ID 页面为真实园区、负责人、漏斗、公海、详情和房源操作工作台。
- 契约与证据：更新 OpenAPI、pytest/PG 并发、Vitest/Playwright、旧能力处置、字段映射、ETL 和全量本地验收。
- 不包含生产数据库/部署、真实 radar 爬虫、企微回调、自动外呼/触达、AI 评分、真实第三方凭据或未经授权的旧数据。
