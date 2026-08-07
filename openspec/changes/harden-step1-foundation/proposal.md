## Why

Step1 已具备可运行的 Identity、Park、Unit 骨架和租户/园区隔离基础，但登录仍向所有用户授予全园权限，角色与园区范围没有进入授权链路，异常、日志、审计和规范测试也未闭环。若直接进入 Party/Lease 开发，这些基础缺口会被复制到后续核心交易模块，因此需要先完成基础加固。

## What Changes

- 登录按租户解析用户，并从角色、权限和用户/角色园区范围计算 JWT 授权信息，不再硬编码 `permissions=["*"]`。
- 补齐 RBAC 最小持久化模型、默认管理员角色与权限种子，同时保持本地开发可启动。
- 增加权限码依赖，保护 Park/Unit 写操作；园区数据范围继续由 Repository 强制执行。
- 统一 FastAPI 校验错误和未捕获异常响应为 `{code,message,data}`，修复非法状态导致 500 的问题。
- 增加 `X-Request-Id` 中间件、结构化业务日志与关键写操作审计表/服务。
- 增加生产鉴权、RBAC、非法状态、软删除、登录租户歧义、错误 envelope 和审计测试。
- 修正 Step1 完成报告中过期的园区权限描述，并记录真实完成边界。

## Capabilities

### New Capabilities

- `identity-authorization`: 租户内登录、RBAC 权限解析、园区数据范围和接口权限检查。
- `api-resilience-observability`: 统一错误响应、请求关联 ID、结构化业务日志和安全的未知异常处理。
- `foundation-compliance`: 关键写操作审计、基础安全配置校验、测试门禁和文档一致性。

### Modified Capabilities

无。当前仓库没有已发布的 OpenSpec capability。

## Impact

- 代码：`apps/api/app/core`、`shared`、`modules/identity`、`modules/park_property`、数据库模型与 Alembic migration。
- API：`POST /auth/login` 增加可选 `tenant_code`；Park/Unit 写接口开始校验权限码；错误响应格式统一。
- 数据库：新增 permissions、role_permissions、user_roles、role_park_scopes、audit_logs 表。
- 运维：生产环境必须配置非默认 JWT secret；响应增加 `X-Request-Id`。
- 测试与文档：扩充 Step1 自动化测试并同步完成报告。
