## Why

当前系统只提供租户内的通用组织树与园区授权，无法表达产业园运营所需的集团、区域、园区治理链，也缺少岗位任职和字段级数据策略。真实用户因此无法完成“集团建模—区域管辖—园区归属—岗位任职—敏感字段受控查看”的完整管理旅程，独立验收能力矩阵对应项仍为 `MISSING`。

## What Changes

- 建立租户隔离的集团、区域以及区域与园区归属关系，支持启停、排序、层级查询和安全的关系变更。
- 建立岗位主数据和用户任职关系，支持主岗位、任职有效期、组织归属、园区范围校验和历史保留。
- 建立字段访问策略，按角色控制受保护资源字段的 `VISIBLE`、`MASKED`、`HIDDEN` 访问效果，并提供后端统一解析与响应投影能力。
- 提供组织治理 REST API、权限码、事务审计、并发/唯一性约束和一致的租户及园区隔离。
- 重建 PC 系统管理中的组织治理工作区，使管理员可在真实 API 上维护集团、区域、园区归属、岗位、任职和字段策略，并具备加载、空态、错误、权限、冲突和重试状态。
- 增加 PostgreSQL 16 迁移、OpenAPI、单元/仓储/API/浏览器 E2E 以及合成迁移就绪证据；不连接旧生产库，也不把未经授权的旧数据演练记为完成。

## Capabilities

### New Capabilities

- `organization-hierarchy-governance`: 集团、区域及园区归属的租户级治理模型、规则、API 与审计。
- `position-assignment-governance`: 岗位主数据、用户任职、有效期、主岗位和作用域约束。
- `field-access-policy`: 角色级字段可见、脱敏、隐藏策略以及服务端统一投影语义。
- `organization-governance-pc`: PC 端可操作的组织治理工作区及其真实 API 状态处理。

### Modified Capabilities

- `identity-authorization`: 新增组织治理动作权限与字段策略必须从当前租户的数据库授权关系解析，不能由客户端声明。
- `park-scope-model`: 区域与园区归属不自动扩大用户园区数据范围，所有园区级组织治理操作仍须同时满足显式园区授权。

## Impact

- 后端：`apps/api/app/modules/identity`、新的平台组织治理应用/仓储边界、共享字段投影组件、权限种子与审计。
- 数据库：新增不可修改历史迁移之后的 Alembic revision；新增集团、区域、园区归属、岗位、任职、字段策略表及约束/索引。
- API：新增 `/system/organization-governance/*` 资源，并更新 OpenAPI 契约。
- PC：扩展 `apps/web/src/views/SystemAdminView.vue`、API 类型与真实交互。
- 测试与证据：pytest、PostgreSQL 16、真实 HTTP、Playwright、迁移和视觉证据；外部旧库仍保持独立阻塞。
