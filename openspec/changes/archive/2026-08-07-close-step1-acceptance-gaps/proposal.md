## Why

Phase06-Step1 已有条件通过验收，但暴露了五类会在 Party/Lease/Bill 前被复制放大的基础缺口：本地 Alembic current 落后于唯一 head；local/test 种子使用固定管理员明文密码；动作权限码 `*` 被错误兼作全园区数据范围；Application 直接构造 ORM 违反冻结分层规范；日志字段与 OpenAPI 严格校验未闭环。当前必须先用独立 OpenSpec 变更关闭这些缺口，再允许进入 Party 设计/实现。

## What Changes

- 建立 **本地 SQLite 迁移闭环** 操作规范与任务：备份 → 确认 DATABASE_URL → `alembic upgrade head` → 校验 revision/数据/表 → 全量测试 → 回滚方案（本变更提案阶段只写任务，**不执行迁移**）。
- **移除源码中的固定管理员明文密码**；local 仅从环境变量读取初始化密码；test 由 fixture 注入；production 禁止自动种子；已存在管理员幂等且不重置密码。
- **权限码与园区范围彻底分离**：`permissions=["*"]` 仅表示全部动作权限；全园区访问必须由独立园区授权语义表达；空园区范围默认拒绝。
- **修复 Application 直接构造 ORM 的分层违规**：Domain 纯业务、Repository 面向领域对象/DTO、Infrastructure Mapper 转换；Identity/Park/Unit 最小安全重构顺序；增加架构依赖检查防回归。
- **日志字段统一**（`business_module` → `module` 或兼容双写）与 **OpenAPI 3.1 严格校验**及运行时路由一致性核对。
- **Git 保护方案**仅输出操作建议（初始化、.gitignore、基线提交）；**不执行** git init/commit/push。

**BREAKING（行为）**

- 仅拥有 `*` 动作权限、**无**全园区范围授权的用户，将 **不再** 自动获得全部园区数据访问（需迁移 ADMIN 种子与测试数据）。

**Non-Goals**

- 不执行 `openspec-apply-change` / 不改业务代码（本阶段仅 proposal/design/specs/tasks）。
- 不开发 Party / Lease / Bill / Payment。
- 不连接旧 Java 数据库。
- 不配置远程 Git 仓库、不推送 GitHub。

## Capabilities

### New Capabilities

- `step1-db-migration-ops`：新系统 SQLite 迁移闭环、备份/回滚、revision 与数据校验、禁止旧库连接。
- `secretless-bootstrap`：local/test 种子凭据来源、禁止源码固定密码、production 禁种、幂等不重置密码。
- `park-scope-model`：园区范围独立模型（全园区/指定园区/拒绝）、与动作权限分离、合并规则与测试矩阵。
- `layered-architecture-enforcement`：Domain/Application/Infrastructure 边界、Mapper、禁止 Application 构造 ORM、架构依赖测试。
- `observability-contract-hardening`：日志 module 字段统一、OpenAPI 严格校验、路由与契约一致性。
- `local-git-hygiene`：.gitignore、基线提交建议、敏感/DB 文件不入库（仅流程规范，不执行 git）。

### Modified Capabilities

- `identity-authorization`：登录签发的 claims 中 `*` 不再隐含全园区；园区范围独立计算；ADMIN 种子兼容迁移。
- `foundation-compliance`：bootstrap 密码来源、迁移验收项、失败场景与审计相关说明对齐。

## Impact

- 代码（apply 阶段）：`bootstrap`、`TenantContext`/`deps`、`AuthService`/`AuthorizationRepository`、Park/Unit Service 与 Repository、logging、可选架构 lint/test、`.env.example`。
- 数据库：仅对 **新系统** `D:\重构python\kwzy-python\apps\api\kwzy_step1.db` 升级到 head `8c2f4aa10b7d`；可能新增园区范围表达字段/表（若设计采用 scope_type）。
- API：对外路径尽量兼容；授权结果可能变严（无园区范围用户读列表为空/403）。
- 运维：local 需配置初始化密码环境变量；升级前强制 DB 备份。
- 文档：工程规范中与 `*` 全园相关的表述需同步（apply 阶段）。
- 测试：扩展授权矩阵与分层依赖检查。
