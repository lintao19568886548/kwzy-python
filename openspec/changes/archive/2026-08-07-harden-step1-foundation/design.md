## Context

Step1 当前以 FastAPI + SQLAlchemy 模块化单体运行，Repository 已强制 tenant/park 过滤，但 Identity 登录直接在接口层查询 User，并向任何成功用户签发 `permissions=["*"]`。Role 与 UserParkScope 表尚未进入授权计算；AppError 之外的校验/未知异常没有统一 envelope；业务写操作没有 request_id、结构化日志和 audit_logs 落库。

本变更必须保持现有 `/api/v1` 路径、SQLite 本地开发和 MySQL 生产兼容，不连接旧 Java 数据库，也不实现 Party/Lease/Bill/Payment。

## Goals / Non-Goals

**Goals:**

- 建立最小可用的租户内 RBAC：角色权限、用户角色、用户/角色园区范围。
- 由数据库授权关系生成 JWT claims，并在 Park/Unit API 执行权限码检查。
- 所有对外异常返回稳定 envelope，未知错误不暴露内部细节。
- 为请求和关键写操作提供 request_id、JSON 日志和同事务审计记录。
- 通过自动化测试证明生产鉴权、权限拒绝、隔离、错误响应和审计行为。

**Non-Goals:**

- 不增加 refresh token、短信登录、page-access 或动态菜单 API。
- 不开发 Party、Lease、Billing、Collection 等业务。
- 不引入 Redis、消息队列、第三方日志 SDK 或外部身份提供商。
- 不改变共享库 `tenant_id` 隔离策略，不实现独立库路由。

## Decisions

### 1. 采用数据库关系解析授权，不信任客户端 claims

新增全局 Permission 字典，以及 RolePermission、UserRole、RoleParkScope ORM；继续使用现有 UserParkScope。登录时根据 `tenant_code + username` 定位用户，权限取所有有效角色权限并集，园区范围取用户直接范围与角色范围并集。JWT 仅承载该次登录解析出的快照。

备选方案是继续由配置或用户名硬编码管理员权限；该方案无法测试租户授权，也会把安全债务复制到后续模块，因此拒绝。

### 2. 权限码与数据范围分离

权限码控制“能否执行动作”，园区范围控制“能操作哪些数据”。Park/Unit 读写分别使用 `park:read`、`park:write`、`unit:read`、`unit:write`；`*` 代表显式平台/租户超级权限。Repository 仍是 tenant/park 过滤的最终防线。

### 3. 默认管理员通过正常 RBAC 种子获得 `*`

`ensure_default_tenant` 幂等创建默认 Permission、ADMIN Role、RolePermission 和 UserRole。已有默认租户/用户也会补齐关系，避免本地数据库升级后无法登录。生产环境不自动调用该种子。

### 4. Identity 接口下沉到 Application + Infrastructure

登录编排进入 AuthService，授权查询进入 AuthorizationRepository。接口层仅接收 DTO、调用 Service、包装响应，以符合冻结的分层规范。

### 5. 请求关联与异常采用标准库实现

HTTP 中间件读取或生成 `X-Request-Id`，写入 request state/contextvar，并在响应回写。标准库 logging 使用 JSON Formatter 输出固定字段。注册 RequestValidationError 和 Exception handler，分别返回 `VALIDATION_ERROR` 与 `INTERNAL_ERROR` envelope。

### 6. 审计与业务写入同事务

新增 AuditLog ORM 与 AuditRecorder。Park/Unit 创建、修改、状态变更、删除在同一 Session 中先写审计再 commit；任一写入失败整体回滚。detail 只保存必要的状态摘要，不记录密码、Token 或完整敏感字段。

### 7. 生产配置启动即失败

当 `APP_ENV=production` 时，默认 JWT secret 或通配 CORS 属于无效配置，Settings 校验直接阻止应用启动。这样比运行时告警更能防止误部署。

## Risks / Trade-offs

- [JWT 权限快照在过期前不会感知角色变更] → 当前 access token 仅 30 分钟；刷新/撤销在后续 Identity change 中实现。
- [RBAC 新表使已有数据库需要迁移] → 提供独立 Alembic revision；本地 create_all 只作为开发兜底。
- [默认管理员补种会扩大本地 admin 权限] → 仅 local/test lifespan 执行，production 禁止自动种子。
- [JSON 日志可能改变本地输出习惯] → 保留 DEBUG 开关，字段契约稳定，测试不依赖具体输出顺序。
- [审计增加一次同事务 INSERT] → Step1 写入量很小，优先保证一致性；后续高吞吐场景再评估 outbox。

## Migration Plan

1. 应用 Alembic migration，创建 RBAC 与 audit_logs 表。
2. 在 local/test 启动时由幂等 bootstrap 补齐默认管理员授权。
3. 配置生产 JWT secret 和明确 CORS origin 后部署新代码。
4. 运行全量 pytest，验证旧 Park/Unit 流程与新授权/审计测试。
5. 回滚时先回退应用代码，再执行 migration downgrade 删除新增表；现有业务表不变。

## Open Questions

- refresh token、权限即时失效和管理员管理 API 留待后续独立 Identity change。
- Party 开发前仍需确认它保持 Lease 上下文内聚合，不在本变更处理。
