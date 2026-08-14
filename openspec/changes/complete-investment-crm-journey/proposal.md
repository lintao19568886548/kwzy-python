## Why

当前招商 CRM 已覆盖去重、人工分配/改派、公海、跟进活动、房源匹配、限时锁与转化，但仍缺少可治理的自动分配、真正的带看预约、受审批中心约束的意向申请，以及安全幂等的外部渠道接入。能力矩阵第 4 项因此仍为 `MISSING`，现有“可操作”页面不能被当作完整招商闭环。

## What Changes

- 新增园区级版本化自动分配规则、成员资格/容量、确定性预览与并发安全执行；支持创建、渠道接入和公海回收后的自动分配，并保留人工改派覆盖。
- 新增带看预约、确认、到场完成、取消与爽约状态机，关联一个或多个当前出租单元，完成后以不可变活动事实推进招商阶段。
- 新增版本化招商意向申请，冻结单位、面积、期限、报价等快照，提交到现有审批中心的 `LEAD_INTENT` 流程；审批结果是锁房与带合同转化的权威门禁。
- 新增禁用优先的外部渠道配置与签名接收箱；以时间窗、HMAC、幂等键、载荷摘要、限长字段、隔离/重放和审计抵御伪造、重放和数据污染，不宣称任何厂商已联调。
- 扩展 PC 招商工作台，提供分配规则、带看日程、意向/审批状态和渠道接收箱的真实 API 视图，以及 loading、empty、403、409、offline/retry 和响应式状态。
- 新增 PostgreSQL 16 前向迁移、真实 HTTP/浏览器/并发/安全测试和合成迁移演练；真实旧库与真实渠道联调继续保持外部门禁。

## Capabilities

### New Capabilities
- `lead-assignment-rule-governance`: 园区级版本化自动分配规则、成员容量、预览、确定性选择和并发执行。
- `lead-viewing-management`: 带看预约、参与人、房源、确认、完成、取消、爽约和活动时间线一致性。
- `lead-intent-approval`: 招商意向快照、审批提交、状态投影、锁房/转化门禁和版本历史。
- `lead-channel-intake`: 禁用优先的签名渠道接收、幂等、隔离、重放和未联调边界。

### Modified Capabilities
- `investment-leads`: 创建线索可按已发布规则自动归属，并保留来源与分配证据。
- `lead-assignment-pool`: 从仅人工分配扩展为规则驱动自动分配、容量回退、公海兜底与人工覆盖。
- `lead-activity-pipeline`: 带看完成事实与阶段/SLA/待办投影保持一致。
- `unit-opportunity-locking`: 新锁与续期受已批准意向、单元快照和并发约束门禁。
- `investment-crm-pc`: 工作台增加自动分配、带看、意向审批和渠道接收箱控制面。
- `investment-crm-data-migration`: 增加分配规则、带看、意向和渠道接收记录的迁移处置与对账。
- `identity-authorization`: 增加分配规则、带看、意向和渠道管理的数据库派生权限边界。

## Impact

- 后端：Investment 领域实体/服务/仓储/API，Workflow 审批适配，WorkItem/事件/审计投影，配置和安全中间件。
- 数据库：在当前唯一 Alembic head 后新增前向迁移，不修改已应用历史迁移；增加复合租户外键、条件唯一、版本和幂等约束。
- 前端：`apps/web` 招商工作台、API 类型、路由与 Playwright 旅程。
- 契约与交付：OpenAPI、OpenSpec、合成 ETL、真实 HTTP、PG16 并发、性能、备份恢复、视觉证据和能力矩阵。
- 外部边界：只验证本地签名协议与 sandbox/fake 契约；未取得真实厂商协议/凭据前保持 `NOT_CONNECTED/BLOCKED_EXTERNAL`，不连接生产。
