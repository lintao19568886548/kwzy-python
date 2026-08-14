## Context

独立验收确认当前 Python 系统已有 `tenants`、`org_units`、`parks`、用户/角色/园区授权和事务审计，但组织架构只有通用部门树，无法表达集团与区域的经营管辖，也没有岗位任职和字段级授权。旧系统证据包含 `organization/OrganizationController.java`、`system/region/SystemRegionController.java`、`system/dept/SystemDeptController.java` 及对应 PC 页面；蓝图又要求集团、区域、园区和岗位形成可治理链。此变更涉及数据库、授权、API 与 PC，且字段策略属于安全边界，必须先冻结设计。

约束：继续使用共享库 `tenant_id` 行级隔离；动作权限与园区数据范围正交；应用启动不得 `create_all`；不得修改已应用迁移；不得连接旧生产库；所有写操作必须同事务落审计。

## Goals / Non-Goals

**Goals:**

- 在一个租户内表达集团、区域和园区当前归属，同时保留园区调区历史。
- 通过岗位与任职记录表达用户在组织/园区中的职责，支持有效期和唯一主岗位。
- 以角色为主体配置受保护字段的可见、脱敏和隐藏策略，并在用户列表这一真实资源上服务端执行。
- 提供完整的仓储、应用服务、REST、PC、Alembic、PostgreSQL、HTTP 和浏览器证据。
- 保持现有 JWT 动作权限和显式园区 scope 语义不被组织层级隐式放大。

**Non-Goals:**

- 不在本变更实现 SaaS 租户开通、邀请、独立数据库复制或生产组织迁移。
- 不实现通用 BPM、审计中心、消息中心或多角色工作台，这些由后续纵切完成。
- 不让岗位自动授予角色、权限或园区 scope；任职是业务治理数据，不是隐式授权通道。
- 不伪造旧库映射、外部凭据或生产联调结果。

## Decisions

### 1. 集团与区域使用独立聚合，部门树继续保留

新增 `organization_groups` 和 `organization_regions`，区域通过 `group_id` 属于集团；现有 `org_units` 继续表示部门/团队。这样避免给历史 `org_units` 强加多种层级语义，也允许岗位继续归属部门。

备选方案是把集团、区域和部门都塞进 `org_units.type`。未采用，因为跨类型父子约束、园区调区历史和旧数据兼容会变得含混。

### 2. 园区归属使用有效期关系而非覆盖外键

`region_park_assignments` 保存 `effective_from/effective_to`，数据库用 PostgreSQL 部分唯一索引保证同租户同园区只有一条当前关系。调区在同一事务中锁定并关闭旧关系、创建新关系、写审计；列表默认返回当前关系，历史端点返回完整链。

备选方案是在 `parks` 增加 `region_id`。未采用，因为无法证明历史，也无法安全演练调区和回滚。

### 3. 任职与 RBAC 明确分离

`positions` 归属可选 `org_unit_id`；`user_position_assignments` 关联用户、岗位、可选园区、有效期和 `is_primary`。数据库约束当前重复任职与当前主岗位唯一；应用层校验用户、岗位、部门、园区同租户，并对园区执行 `TenantContext.allows_park`。

岗位不生成 `user_roles`、`user_park_scopes` 或 JWT claims。权限仍由现有角色体系显式配置，避免“把人调岗即越权”。

### 4. 字段策略采用服务端白名单和拒绝优先合并

`field_access_policies` 只允许配置代码白名单内的 `(resource_type, field_name)`。首个真实落点是 `USER.phone`；后续领域可注册更多字段。模式为 `VISIBLE`、`MASKED`、`HIDDEN`，多角色合并采用 `HIDDEN > MASKED > VISIBLE`，没有显式策略时受保护字段默认 `MASKED`。`*` 动作权限不绕过字段策略。

`MASKED` 由注册表选择确定性掩码函数；`HIDDEN` 从响应对象删除字段。策略只在服务端投影，客户端传入的权限或模式被忽略。该选择以最小披露为默认，代价是新增受保护字段时管理员需要显式配置可见策略。

### 5. 组织治理作为 IdentityAccess 内的独立四层子模块

API 仍挂在 `/api/v1/system/organization-governance`，但实现放在 `modules/identity/{interface,application,infrastructure}` 的专用文件中，Router 只做 Schema/Depends/调用；查询在 Repository；规则和事务在 Service。复用现有 `AuditRecorder`、`TenantContext` 和统一错误 envelope。

### 6. PC 采用系统管理中的独立“组织治理”标签

现有系统管理页面扩展一个真实 API 驱动的标签，分为层级、岗位任职、字段策略三个面板。页面必须提供创建/调区/结束任职/保存策略动作及加载、空态、403、409、错误重试反馈；窄屏改为单列，表格可横向滚动。

## Risks / Trade-offs

- [并发调区或主岗位重复] → PostgreSQL 部分唯一索引、行锁、冲突映射为 409，并增加并发测试。
- [字段策略误配导致泄露] → 保护字段白名单、默认脱敏、拒绝优先、服务端投影和跨角色测试。
- [岗位被误认为授权来源] → API/文档明确分离，测试证明任职不会改变 JWT 权限与园区 scope。
- [SQLite 与 PostgreSQL 部分索引行为差异] → 单元/API 可使用 SQLite，但约束和并发最终以 PostgreSQL 16 标记测试为准。
- [集团/区域停用造成悬挂] → 有活动子区域或当前园区关系时禁止停用；先迁移/关闭依赖。
- [PC 页面继续膨胀] → 本变更保持单独逻辑区和清晰类型；后续可在不改路由契约下拆分组件。

## Migration Plan

1. 新增单一 Alembic revision，创建六张表、外键、检查约束、唯一约束和查询索引；历史 migration 不修改。
2. `upgrade head` 后为空租户保持空数据，不自动伪造集团或区域；本地 bootstrap 只补权限字典。
3. 部署 API 与 PC，先由管理员创建集团/区域，再建立园区归属、岗位、任职和字段策略。
4. 合成迁移工具只验证规范化映射、幂等、对账和回滚；真实旧库须等授权 schema/脱敏快照。
5. 回滚时先确认新表无生产依赖，再 `downgrade -1` 删除本 revision 所建对象；不改现有 `parks/org_units/users/roles`。

## Open Questions

- 真实旧库中集团与 SaaS `organization` 是否一一对应，需授权 schema dump 后确认；当前不阻塞新模型与合成演练。
- `USER.phone` 之外的受保护字段清单将在各后续领域纵切中按业务证据逐项注册，禁止提前猜测并批量开放。
