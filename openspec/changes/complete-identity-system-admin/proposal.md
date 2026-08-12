## Why

Phase06 已将 Party / Lease / Bill / Payment 核心链路合入 `main`，但 V2.3.2 全量审计结论仍为 **CONDITIONAL**：旧 Java 约 481 个 canonical 接口中，Identity/System/Admin 后台能力（登录会话、用户/角色/菜单、园区范围授权、租户组织入口等）绝大多数仍为 **MISSING / PARTIAL / REDESIGNED**，前端管理端也未替换。若跳过 Identity 管理与会话安全直接扩张其他业务域，将无法支撑真实运营切换、审计与租户隔离，且会把 JWT 快照权限、刷新吊销、菜单动作权限缺口复制放大。

本变更只进入 **设计/规范** 阶段，关闭 Identity/System/Admin 的证据与方案缺口，**不**执行 apply、**不**宣称全量 Java/前端替换完成。

## What Changes

- 建立 Identity/System/Admin **接口级证据基线**（Java controller/service/repo 行号、前端 API/路由链路、契约差异、字段映射、Python 现状核对）；证据产物位于仓库外 `review-artifacts/identity-system-admin-evidence/`。
- 定义完整认证与会话能力：密码登录、刷新令牌、吊销/登出、密码修改、（可选）短信登录与页面二次验证——策略待人工决策后落地。
- 定义用户/角色/权限/菜单/园区范围的 **管理 API** 与 RBAC 执行模型；明确 `*` 仅表动作全权限、全园区须独立 scope。
- 定义 JWT claims 快照 vs 权限即时生效策略、审计与敏感字段策略。
- 定义相对旧 Java 路径的 **兼容/适配** 策略与 Identity 数据迁移设计边界（不连接生产库）。
- 将现有 `identity-authorization` / `auth-fail-closed` / `park-scope-model` 等能力扩展为可运营的管理后台能力集。

**BREAKING（仅在未来 apply 时可能出现，本阶段不落地）**

- 刷新/登出、用户角色变更后的令牌失效策略可能导致旧前端 cookie/`jwt` 行为不兼容。
- 菜单与动作权限拆分后，仅有菜单无动作码的访问将被拒绝。
- 响应 envelope 与路径前缀（`/api/v1/...`）相对旧 `/api/...` 可能不 1:1。

**Non-Goals（本阶段明确不做）**

- 不 `openspec apply`、不编写业务代码、不新增/执行 Alembic migration。
- 不开发 Party/Lease/Bill/Payment 增量、Finance/RentVerify/Investment/HRM/门禁等。
- 不替换旧前端 playground 全量页面。
- 不连接旧 Java 生产库、不执行 ETL cutover。
- 不决定短信供应商、多库拓扑、PII 密钥体系的生产最终方案（列入 Open Questions）。

## Capabilities

### New Capabilities

- `identity-authentication`：密码登录、令牌签发、可选短信/验证码登录入口的需求边界。
- `user-lifecycle-management`：用户 CRUD、启停、密码重置/修改、用户名唯一性等。
- `role-permission-management`：角色 CRUD、角色-权限绑定、权限码模型。
- `menu-page-access-control`：菜单树、动态菜单、页面权限与动作权限关系。
- `tenant-park-authorization`：租户识别、用户/角色园区范围、与 `*` 分离。
- `token-session-security`：refresh、logout/revoke、JWT 失效与会话安全。
- `identity-audit-observability`：登录/管理写操作审计、失败审计、敏感字段策略。
- `legacy-identity-compatibility`：旧路径/契约适配、弃用与兼容窗口。
- `identity-data-migration`：Identity 相关表字段映射与迁移门禁（schema-only、人工决策）。

### Modified Capabilities

- `identity-authorization`：从“登录 claims + 业务 API 强制”扩展为含管理面与会话生命周期的完整授权需求（delta）。
- `park-scope-model`：补充管理 API 对 all_parks / LIST / NONE 的可配置写入语义（delta）。
- `foundation-compliance`：补充 Identity 管理写路径的审计/错误 envelope 期望（delta，若与现规范冲突则以本 change 为准并在 apply 前合并）。

## Impact

- **代码（仅 apply 阶段）**：`apps/api/app/modules/identity/**`、`shared/deps.py`、`core/security.py`、可能的 session/refresh 表、audit 记录点、OpenAPI `docs/04-api/**`。
- **数据库（仅 apply 阶段）**：PostgreSQL 16 权威；可能新增 refresh_token / session / menu / 管理审计相关表；SQLite 仅测。
- **API**：新增管理类路由；现有 `POST /api/v1/auth/login`、`GET /api/v1/auth/me` 行为可能增强但不得削弱 fail-closed。
- **前端**：本阶段只定义契约与调用链证据；不交付新前端。
- **迁移/安全**：密码哈希算法、refresh 存储、短信与 PII 需人工决策后方可实现。
- **证据**：`identity-system-admin-evidence-v2.2`（可独立复验：`accept_identity_review_v2_2.py --package-root .`；含 481 母表 + source-evidence 快照）。

## Evidence Snapshot (Identity evidence V2.3.2)

| Metric | Value |
|---|---|
| Mother inventory | **481** rows；scope reconciliation **set-equal** |
| INCLUDE_IDENTITY | **74**（= endpoints = contracts stable_id sets） |
| VersionController | **INCLUDE_IDENTITY** (`GET /api/system/version`) |
| Service method RESOLVED | **74/74** |
| Persistence | FULLY **39** / SQL_PARTIAL **7** / REPO_METHOD **8** / SERVICE_ONLY **20** |
| Repo calls 1:N | **169**（`call_kind`；refresh 6 calls） |
| P0 contracts | **19** per-endpoint auth/tenant/park/PII/errors/payload |
| Identity field rows | **52**（MAPPED/TRANSFORM/HUMAN）；target fields separate |
| Python Identity | **2** login/me PARTIAL；COMPLETE=0 |
| FE CLOSED | **0** |

Apply **NOT_APPROVED**。Java/FE 全量替换未完成；数据迁移 BLOCKED。

## Apply Gate

本 change **仅设计**。人工评审通过后才可另批 apply。在此之前：

```text
IDENTITY_SYSTEM_ADMIN_APPLY=NOT_APPROVED
KWZY_NEXT_PHASE_APPLY=NOT_APPROVED
```


## Evidence package V2.3.2

Design references Identity/System/Admin evidence pack **V2.3.2** (field-level P0/PII, read-only acceptance, final-state source replay). Implementation tasks remain unchecked. IDENTITY_SYSTEM_ADMIN_APPLY=NOT_APPROVED.
