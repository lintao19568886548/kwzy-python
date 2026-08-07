## Context

Step1 验收结论为**有条件通过**。代码与 OpenSpec change `harden-step1-foundation` 已完成 14 项任务并通过 23 个 pytest，但验收报告明确了残留缺口：

1. Alembic 唯一 head 为 `8c2f4aa10b7d`，本地 `kwzy_step1.db` 的 current 仍为 `44cb70117ff4`。  
2. `ensure_default_tenant` 使用固定明文生成管理员密码哈希。  
3. `TenantContext.has_all_park_access` 将 `permissions` 中的 `*` 视为全园区，与“权限码 vs 数据范围”分离原则冲突。  
4. Application Service 直接构造 SQLAlchemy ORM Model。  
5. 日志字段 `business_module` 与规范 `module` 不一致；OpenAPI 未做严格 Schema 校验。  
6. 目录不是 Git 仓库，缺少基线与 ignore 保护建议。

本 change **只产出设计与任务**；迁移与代码修改在人工评审 proposal/design 后通过 apply 执行。

## Goals / Non-Goals

**Goals:**

- 关闭上述验收缺口的可执行方案与任务清单。  
- 数据库操作仅针对新系统 SQLite；禁止旧 Java 库。  
- 授权模型：动作权限与园区范围正交。  
- DDD 分层可执行、可测试、可防回归。  
- 日志与 OpenAPI 契约可验证。  
- Git 初始化建议可操作但不在本 change 自动执行。  

**Non-Goals:**

- 不在 propose 阶段执行 migration、改代码、改 DB、git init。  
- 不实现 Party/Lease/Bill/Payment。  
- 不实现失败审计持久化（可列为后续；本 change 可选仅文档化）。  
- 不引入 Redis/MQ/新身份提供商。  

## Decisions

### 1. 数据库版本闭环（运维任务包，非新 migration 必选项）

**决策：** apply 阶段以 **操作 runbook + 自动化校验脚本/测试** 关闭 gap，而非再生成一条空 migration。现有 head `8c2f4aa10b7d` 已包含 RBAC/audit 表。

**步骤（apply 时执行）：**

1. 确认 `DATABASE_URL` 为 `sqlite+pysqlite:///./kwzy_step1.db` 或等价新系统路径；绝对路径必须落在 `...\kwzy-python\apps\api\` 下。  
2. 拒绝 URL 含旧主机/库名模式（如生产 magic 库、已知旧 Java 连接串）；校验失败中止。  
3. 备份：`copy kwzy_step1.db → kwzy_step1.backup.YYYYMMDD-HHMMSS.db`（同目录）。  
4. `alembic upgrade head`。  
5. `alembic current` 必须等于 `alembic heads` 且 heads 唯一。  
6. 数据抽检：tenants/users/parks/units 行数与关键 code 在升级前后一致（备份对比或 pre-count）。  
7. 表存在性：`permissions`、`role_permissions`、`user_roles`、`role_park_scopes`、`audit_logs`。  
8. 全量 `pytest`。  
9. **回滚：** 停止应用 → 用备份文件覆盖 `kwzy_step1.db` →（可选）`alembic downgrade 44cb70117ff4` 仅在代码已回退且确认安全时；优先 **文件级恢复**。  

**风险：** SQLite 升级中断导致半升级状态 → 必须先备份，失败直接文件还原。

### 2. 移除固定管理员明文密码

**决策：**

| 环境 | 行为 |
| --- | --- |
| `local` | 仅当 `LOCAL_ADMIN_PASSWORD`（或约定名）**非空**时创建/补齐 admin 用户哈希；缺失则 **明确失败或跳过种子并打 ERROR 日志**，禁止静默回落固定密码 |
| `test` | 测试 fixture / 环境变量提供凭据；不在业务源码写死明文 |
| `production` | **禁止**调用 `ensure_default_tenant` 自动种子（保持现状并加断言/测试） |

规则：

- 源码、`.env.example`、文档、日志、审计、API **均不得**出现真实密码。  
- `.env.example`：`LOCAL_ADMIN_PASSWORD=` 占位，无示例口令。  
- **已存在 admin 用户：幂等跳过密码字段，绝不 reset。**  
- 新建 admin 时 `password_hash = hash(env_password)`。  

### 3. 权限码与园区范围彻底分离

**决策（推荐方案）：引入显式全园区标志，停止用 `*` 推导全园。**

#### 3.1 动作权限

- `permissions` 列表仅表示动作权限。  
- `*` = 全部动作权限（park/unit/未来 party…）。  
- `has_permission(code)`：`*` 或精确匹配。  

#### 3.2 园区范围（独立）

引入 `TenantContext` 字段（二选一，apply 时实现其一，推荐 A）：

**方案 A（推荐，改动面小）：**

```text
park_scope_mode: "NONE" | "LIST" | "ALL"
park_ids: list[int]   # LIST 时有效；ALL/NONE 时忽略列表内容或保持空
```

- `has_all_park_access` ⇔ `park_scope_mode == "ALL"`  
- `allows_park(id)`：ALL → true；LIST → id in park_ids；NONE → false  
- **空 park_ids + LIST/NONE → 拒绝**，不代表全园  

**方案 B：** 独立表/列 `scope_type` on user 或 membership（更重，留二期）。

本 change 采用 **方案 A**，登录时由 AuthorizationRepository 计算：

```text
若用户（经租户过滤）拥有“全园区”授权标记 → ALL
否则 park_ids = user_park_scopes ∪ role_park_scopes（同租户）
若 park_ids 非空 → LIST
否则 → NONE
```

**全园区授权如何持久化（兼容 ADMIN 种子）：**

- 新增全局权限码 **不用于动作**？避免混淆。  
- 更好：新增 `role_park_scopes` / `user_park_scopes` 的哨兵约定 **或** 新表字段 `grant_all_parks`。  

**推荐持久化：** 在 Role 上增加 `all_parks: bool`（tenant 内角色级），ADMIN 种子 `all_parks=true`。  
User 级可选 `users.all_parks`（默认 false）。  
解析：`user.all_parks OR any(role.all_parks for user's roles)` → `park_scope_mode=ALL`。

**合并规则：**

1. 动作权限 = 所有有效角色权限 code 并集。  
2. 园区：若任一级 all_parks → ALL；否则并集 user 直接园区 ∪ 角色园区。  
3. 全部计算强制 `tenant_id` 过滤，禁止跨租户 join。  

**BREAKING 兼容：**

- 旧 JWT 若仅 `*` 且 park_ids=[]：升级后客户端需重新登录。  
- 旧逻辑“`*` ⇒ 全园”删除；ADMIN 种子迁移为 `all_parks=true` + 权限仍含 `*`（动作）。  
- 测试数据：有 `*` 无 all_parks 的用户只能做动作但 list 园区为空/拒绝。  

### 4. Application 不得直接构造 ORM

**决策：引入最小领域对象 + Mapper，不重写业务语义。**

| 层 | 职责 |
| --- | --- |
| domain | `ParkEntity`/`UnitEntity`（dataclass）、状态机（已有 states） |
| application | 操作 Entity/命令 DTO；调用 repository 接口 |
| infrastructure | ORM Model；`ParkMapper.to_entity/to_model`；Repository 实现 |

**违规点评估（当前）：**

| 区域 | 违规 |
| --- | --- |
| ParkService | 直接 `Park(...)`、`session.commit`、返回 dict |
| UnitService | 直接 `Unit`/`Building(...)` |
| AuthService | 较好（Repository 返回 User ORM，可逐步改为 UserEntity） |
| bootstrap | 直接 ORM 种子（允许留在 infrastructure/bootstrap，但密码规则仍适用） |

**最小安全重构顺序：**

1. Park create/update/get 路径 Entity+Mapper  
2. Unit + Building 默认楼  
3. Auth 返回值保持 API 兼容；User ORM 可暂留 repository 边界内  
4. 架构测试：扫描 application 层禁止 `from app.infrastructure.database.models`（bootstrap/脚本白名单）  

**兼容：** HTTP 响应字段与表结构不变。  

### 5. 日志字段与 OpenAPI

**决策：**

- Logger `extra` 统一使用 **`module`** 作为规范字段名。  
- 过渡：JSON formatter 同时输出 `module`；若历史依赖 `business_module`，formatter 可双写同一值一个版本周期。  
- 增加 dev 依赖或 CI 步骤：`openapi-spec-validator`（或兼容工具）校验 `docs/04-api/openapi-v1-core.yaml` OpenAPI 3.1。  
- 任务：人工/脚本比对 FastAPI 路由表与 yaml paths（Step1 范围：auth/parks/units）；**不扩展 Party API**。  

### 6. Git 保护（仅建议）

**决策：** 输出 runbook，**不执行**。

1. 检查并 ignore：`.env`、`*.db`、`*.backup.*`、`.venv`、`__pycache__`、日志、IDE、密钥。  
2. 完善根目录 `.gitignore`。  
3. `git init` 于 `kwzy-python`。  
4. 创建 Step1 基线 commit（信息约定，不 push）。  
5. 无 remote、不推送 GitHub。  
6. SQLite 与备份 **禁止** 提交。  

## Risks / Trade-offs

- [BREAKING：`*` 不再全园] → ADMIN 种子加 `all_parks`；文档与测试明确；要求重新登录。  
- [SQLite 迁移损坏] → 时间戳备份 + 文件级回滚优先。  
- [分层重构回归] → 保持 API 兼容测试全绿；小步 Park→Unit。  
- [env 缺密码导致 local 无法种子] → 明确错误信息，优于静默弱口令。  
- [双写日志字段] → 短期兼容后删除 `business_module`。  

## Migration Plan（apply 阶段顺序）

1. 人工确认 proposal/design。  
2. 数据库备份与 upgrade head + 验证。  
3. 密码环境变量与 bootstrap 改造 + 测试。  
4. 园区范围模型 + ADMIN 兼容 + 授权测试矩阵。  
5. Domain Entity/Mapper 最小重构 + 架构依赖测试。  
6. 日志字段与 OpenAPI 严格校验。  
7. 输出 Git runbook（不强制执行 init）。  
8. 全量 pytest + openspec validate。  

## Open Questions（已定默认）

- 全园区表达：默认 **Role/User `all_parks` 布尔**（见上），不采用哨兵 park_id=-1。  
- local 缺密码：默认 **跳过用户创建并 ERROR 日志**（若库中无 admin 则启动可继续但告警；若产品要求 fail-fast 可在 apply 时配置 `LOCAL_ADMIN_PASSWORD_REQUIRED=true`）。  
- 失败审计：不在本 change 实现，保留为后续 gap。  

## 兼容性影响摘要

| 区域 | 影响 |
| --- | --- |
| API 路径 | 无强制变更 |
| 登录响应 | permissions/park_ids 语义更严；可能多 `park_scope` 字段（可选） |
| 本地启动 | 需配置初始化密码 env |
| 已有 DB | 需 upgrade head；ADMIN 需 all_parks 回填 |
| 旧 Java | 无 |

## 测试矩阵（设计）

| 场景 | 期望 |
| --- | --- |
| alembic current == head | 通过 |
| 升级后 parks/units 行数不丢 | 通过 |
| RBAC/audit 表存在 | 通过 |
| 源码无固定明文密码 | 静态/测试断言 |
| 已存在 admin 不改密码 | 通过 |
| production 不跑种子 | 通过 |
| `*` 动作 + 无园区范围 | 动作权限 true，园区访问 false |
| 有园区无动作权限 | 403 PERMISSION_DENIED |
| `*` + 指定园区 LIST | 仅指定园 |
| all_parks | 全园 |
| 跨租户角色 | 不可见 |
| 跨园访问 | 404/403 |
| application 不 import models | 架构测试 |
| OpenAPI schema validate | 通过 |
| 全量 pytest | 绿 |

## 文件影响范围（apply 预期）

- `apps/api/app/modules/identity/**`
- `apps/api/app/modules/park_property/**`
- `apps/api/app/shared/tenant_context.py`, `deps.py`
- `apps/api/app/core/config.py`, `business_logging.py`, `logging_config.py`
- `apps/api/app/infrastructure/database/**`（可能 all_parks 列 migration）
- `apps/api/tests/**`
- `apps/api/.env.example`
- `docs/**`（规范对齐）
- 可选：`scripts/verify_step1_db.py`、根 `.gitignore`

## 人工确认点

1. 是否接受 **`*` 不再授予全园** 的行为变更。  
2. local 缺 `LOCAL_ADMIN_PASSWORD` 时：跳过 vs fail-fast。  
3. 是否在本 change 增加 `all_parks` 列（推荐）或仅用 JWT 扩展字段而不落库（不推荐）。  
4. Git init 是否由人工在 apply 后执行。  
5. 确认 DATABASE_URL 仅指向新系统 SQLite 后再执行迁移任务。  
