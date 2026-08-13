## Context

### Reconciled baseline

当前实现基线为 `main@d9c0b0b`，本地 PostgreSQL 16 全量验收已在该提交上 18/18 步骤通过。Identity 已具备：

- 数据库密码登录与可选 `tenant_code` 消歧；
- 30 分钟 access JWT，以及只保存 SHA-256 哈希的 opaque refresh token；
- refresh 轮换、旧 token 拒绝、logout、本人改密；
- 用户、角色、动作权限、角色菜单、用户/角色园区范围；
- 动态菜单、组织、字典、系统参数与基础 PC 管理页；
- 生产/预发缺 token 时 fail-closed，星号动作权限与全园区范围分离。

仍存在必须关闭的缺口：

1. access JWT 中已有 `tv`，但受保护请求尚未对数据库用户状态和 `token_version` 做在线校验；停用或管理员重置密码后旧 access token 仍可使用到过期。
2. 用户/角色/菜单写操作尚未使用既有 `AuditRecorder`。
3. 登录缺少跨进程可共享的限流；refresh 旧 token 虽被拒绝，但尚未把已轮换 token 的再次使用当作会话族重放事件处理。
4. 菜单仅 list/create；授权写入对 park/menu 等外键缺少完整的租户归属预校验。
5. PC 角色创建硬编码 `all_parks=true`，没有可用的权限、园区、菜单和用户角色配置体验。
6. refresh token 当前由 PC 存入 localStorage；需要浏览器 cookie 与移动客户端响应体两种安全传输策略。
7. 验证码/页面二次验证、旧 Java 74 接口处置证据和真实身份数据迁移尚未闭环。

### Constraints

- PostgreSQL 16 是权威运行时；SQLite 只用于快速单元测试。
- 不连接或写入旧 Java 生产库，不接入真实短信/微信凭据，不执行生产发布。
- 所有写操作必须租户隔离、权限 fail-closed、使用统一 envelope，并避免在日志/审计中出现密码、refresh token 或验证码。
- PC、员工移动端和租户小程序共享身份领域语义，但传输和交互可按客户端安全能力适配。

## Goals / Non-Goals

**Goals:**

1. 关闭身份会话的即时吊销、重放、限流和审计缺口。
2. 完成用户/角色/权限/菜单/园区授权的后端生命周期和 PC 可用配置闭环。
3. 交付供应商无关的验证码/页面二次验证本地能力，同时对生产外部适配保持 fail-closed。
4. 建立旧接口处置、字段映射、迁移演练和测试证据，使完成状态可复验。

**Non-Goals:**

- 不访问生产数据库或执行生产 cutover。
- 不把 fake 短信、合成迁移数据或本地验收宣称为真实生产联调。
- 不在本 change 中实现组织邀请/租户开通、完整 HRM 或其他业务域。
- 不保留未经处置矩阵确认的旧接口“影子兼容”。

## Decisions

### D1 — 分层与事务边界

接口层只负责 schema、依赖与响应；应用服务编排用例；基础设施仓储构造 ORM 实体。身份管理写操作和 `AuditRecorder` 使用同一个 Session，在一次 commit 中提交或一起回滚。

### D2 — 每个受保护请求验证会话版本

access JWT 保留 tenant、uid、permissions、park scope 和 `tv` 快照。依赖层在每个受保护请求中读取最小用户状态：

- 用户不存在、租户不符或状态非 ACTIVE：401；
- token 的 `tv` 与数据库 `token_version` 不同：401；
- 通过后继续使用 token 内权限和园区范围，避免每次重建完整 RBAC。

这使停用、改密和管理员重置能立即吊销 access token；角色/权限变化仍通过递增用户 `token_version` 对受影响用户即时生效。

备选的纯 JWT 过期策略无法满足高风险操作撤权；每次完整解析 RBAC 则放大查询开销。

### D3 — refresh 轮换与重放

- refresh token 为至少 256 位随机 opaque 值，数据库只保存 SHA-256 哈希。
- 每次 refresh 原 token 原子标记 revoked，并关联 replacement；logout、改密、停用和管理员重置吊销该用户所有活动 refresh。
- 如果已轮换 token 再次出现，视为潜在重放并吊销该用户全部 refresh 会话，返回统一 401，不暴露内部状态。
- 并发 refresh 必须只有一次成功；数据库唯一约束和行级锁/条件更新负责仲裁。

### D4 — 多客户端 refresh 传输

- PC 浏览器：服务端设置 HttpOnly、SameSite=Strict cookie；staging/production 强制 Secure。Web 不持久化 refresh token 到 localStorage。
- 员工移动端/租户小程序：因客户端不具备浏览器 cookie 语义，可从响应体接收 refresh token 并存入平台安全存储。
- 兼容期内 refresh/logout 可接受请求体或 cookie；OpenAPI 明确两种通道，服务端仍执行相同轮换/吊销规则。

### D5 — 登录与验证码限流

使用 PostgreSQL 持久化的安全事件/验证码记录作为共享权威，不使用单进程内存计数。键只保存归一化账号/手机号的 HMAC 或不可逆摘要，并按租户、客户端 IP 和用途执行窗口计数。成功登录可清理连续失败计数；达到阈值返回 429 和稳定错误码。

### D6 — 验证码与页面二次验证

- code 由密码学安全随机源生成，只保存哈希、用途、过期时间、尝试次数和 consumed_at。
- 发送通过平台 SMS provider/outbox 端口；local/test 使用 fake provider，production 配置缺失时启动或调用 fail-closed。
- 验证成功只返回短期、一次性的 page-access proof；高风险业务 API 校验证明的用途、用户、租户和过期时间。
- API、日志和审计均不返回验证码；测试通过依赖注入/捕获 fake provider 验证，不在生产响应暴露 debug code。

### D7 — RBAC、菜单与园区范围正交

- 动作权限码由 API 依赖强制；菜单授权只影响导航。
- 全园区由显式 `all_parks` 表示；`*` 只代表动作权限。
- 用户/角色写入前校验 role、park、menu 均存在且属于调用租户；跨租户引用返回 400/404，不依赖数据库 FK 产生 500。
- 菜单支持 list/create/update/deactivate；有子节点或角色绑定时采用停用而非物理删除。

### D8 — 权限变更即时生效

用户角色、用户园区、角色权限、角色园区、角色菜单或角色状态变化后，对直接或间接受影响用户递增 `token_version` 并吊销 refresh。角色菜单变化同时影响下一次动态菜单请求；动作权限仍由新 access token 快照执行。

### D9 — 审计与敏感数据

成功的用户、角色、菜单、园区授权写操作记录 tenant_id、actor、request_id、action、资源和非敏感差异摘要。失败登录以结构化安全事件记录摘要键、IP、原因族和时间，不记录账号明文之外不必要的 PII，更不记录密码/token/code。用户响应永不包含 password_hash。

### D10 — 旧接口与迁移

V2 主契约为 `/api/v1`。旧 Java 74 个 Identity/System/Admin 接口逐项标记 EXACT_MATCH、COMPATIBLE_REDESIGN、REDIRECT、DEFERRED_WITH_REASON 或 REMOVED_WITH_REASON，禁止用模块级“已覆盖”代替逐接口证据。

V2 目标采用单 PostgreSQL 集群和显式 `tenant_id` 隔离。旧库即使多库，也只在 ETL adapter 中处理；在取得脱敏 schema dump 前，真实迁移保持 BLOCKED。密码哈希算法不明时不得静默重置，须选择双验证/登录时升级或受控重置。

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| 每请求用户状态查询增加延迟 | 只查 user id/tenant/status/token_version；后续可用短 TTL 缓存且以版本失效 |
| refresh 并发产生竞态 | PostgreSQL 条件更新/锁、唯一哈希和并发测试 |
| Cookie refresh 引入 CSRF | SameSite=Strict、同源部署、仅 POST、Origin 校验；移动端继续用 body |
| 登录限流可被滥用锁号 | 同时按账号摘要与 IP 限速，使用短窗口/退避，不暴露账号存在性 |
| fake provider 被误当生产 | production 配置 fail-closed，验收状态显式 NOT_LIVE |
| token_version 批量递增成本 | 角色变更只更新绑定用户，使用集合更新并建立索引 |
| 旧密码哈希不可验证 | 真实样本与算法确认前不宣称迁移可切换 |

## Migration Plan

1. 增加安全事件/验证码等所需表和索引，执行 PostgreSQL base→head 与 down/up 演练。
2. 先上线兼容的 body refresh 与在线 token_version 校验，再启用 PC HttpOnly cookie，保留可回滚配置。
3. 完成用户/角色/菜单授权写入和审计，补齐 PC 管理体验。
4. 用合成租户做身份 ETL dry-run、计数/孤儿/唯一性/权限与园区对账。
5. 取得脱敏真实 schema dump 后更新字段映射并做只读迁移演练。
6. 真实短信沙箱、远程预发和生产发布分别等待凭据与人工授权。

**Rollback:** 关闭新增路由/特性开关，回滚 PC cookie 使用，恢复数据库备份；任何 down migration 必须先验证无数据丢失。

## Open Questions

以下只剩外部事实或生产决策，不能由本地实现替代：

1. 旧租户数据库的真实拓扑、schema 和密码哈希算法。
2. 生产短信供应商、模板、签名、回执和限额。
3. 生产域名/跨站部署是否允许 SameSite=Strict；若不允许需完成 CSRF token 方案。
4. PII/KMS 的生产密钥托管、轮换与审计策略。
5. 旧 `/api/*` 的正式退役窗口和客户端版本分布。
