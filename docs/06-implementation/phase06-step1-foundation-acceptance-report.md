# Phase06-Step1 基础加固 — 最终验收报告（只读）

**验收约束：** 验收过程未修改代码、文档、数据库或 Git 状态；未进入 Party/Lease/Bill/Payment。  
**报告日期：** 2026-08-07  

---

## 1. OpenSpec change

| 项 | 值 |
| --- | --- |
| **Change 名称** | `harden-step1-foundation` |
| **工作流类型 / Schema** | `spec-driven`（`.openspec.yaml`） |
| **Change 根路径** | `D:\重构python\kwzy-python\openspec\changes\harden-step1-foundation` |
| **Artifacts** | proposal / design / specs / tasks — **全部完成（4/4）** |
| **CLI 状态** | `openspec list` → **✓ Complete** |
| **最终状态** | **Complete（任务 14/14 已勾选）** |

Capabilities（new）：

- `identity-authorization`
- `api-resilience-observability`
- `foundation-compliance`

---

## 2. 14 项任务完成情况

来源：`openspec/changes/harden-step1-foundation/tasks.md`

| # | 任务 | 状态 |
| --- | --- | --- |
| 1.1 | RBAC + AuditLog ORM | [x] |
| 1.2 | Alembic 迁移 permissions / role 映射 / audit_logs | [x] |
| 1.3 | local/test 默认租户幂等种子 ADMIN + `*` | [x] |
| 2.1 | AuthorizationRepository + AuthService | [x] |
| 2.2 | login `tenant_code` + Identity 走 AuthService | [x] |
| 2.3 | 权限依赖保护 Park/Unit 读写 | [x] |
| 3.1 | Request-Id + JSON 日志 | [x] |
| 3.2 | 校验/未知异常 envelope + 非法状态映射 | [x] |
| 3.3 | 生产 JWT/CORS 校验 | [x] |
| 4.1 | AuditRecorder + 结构化成功日志 | [x] |
| 4.2 | Park/Unit 写操作同事务审计 | [x] |
| 5.1 | 登录/RBAC/拒权/生产鉴权测试 | [x] |
| 5.2 | envelope / request_id / 非法状态 / 软删 / 审计测试 | [x] |
| 5.3 | 文档更新 + 全量隔离测试 | [x] |

**结果：14/14 完成。**

---

## 3. 文件清单（按类别）

> 说明：`kwzy-python` **不是 git 仓库**，无法用 `git status` 区分“本次 diff”。下列按 **当前仓库内与 Step1 基础/加固相关的交付物** 归类（含骨架 + 加固）。

### ORM 与数据库迁移

- `apps/api/app/infrastructure/database/base.py`
- `apps/api/app/infrastructure/database/session.py`
- `apps/api/app/infrastructure/database/repository_base.py`
- `apps/api/app/infrastructure/database/models/__init__.py`
- `apps/api/app/infrastructure/database/models/identity.py`
- `apps/api/app/infrastructure/database/models/park_property.py`
- `apps/api/app/infrastructure/database/models/audit.py`
- `apps/api/alembic.ini`
- `apps/api/alembic/env.py`
- `apps/api/alembic/script.py.mako`
- `apps/api/alembic/versions/44cb70117ff4_step1_identity_park_unit.py`
- `apps/api/alembic/versions/8c2f4aa10b7d_step1_foundation_hardening.py`
- `apps/api/kwzy_step1.db`（本地 SQLite 数据文件）

### Identity 授权

- `apps/api/app/modules/identity/application/auth_service.py`
- `apps/api/app/modules/identity/application/bootstrap.py`
- `apps/api/app/modules/identity/infrastructure/authorization_repository.py`
- `apps/api/app/modules/identity/interface/api.py`
- `apps/api/app/modules/identity/schemas.py`
- `apps/api/app/modules/identity/api.py`（兼容导出）
- `apps/api/app/core/security.py`
- `apps/api/app/shared/deps.py`（含 `require_permissions`）
- `apps/api/app/shared/tenant_context.py`
- `apps/api/tests/test_identity_authorization.py`

### Park/Unit 权限

- `apps/api/app/modules/park_property/domain/states.py`
- `apps/api/app/modules/park_property/application/park_service.py`
- `apps/api/app/modules/park_property/application/unit_service.py`
- `apps/api/app/modules/park_property/infrastructure/park_repository.py`
- `apps/api/app/modules/park_property/infrastructure/unit_repository.py`
- `apps/api/app/modules/park_property/infrastructure/building_repository.py`
- `apps/api/app/modules/park_property/interface/api.py`
- `apps/api/app/modules/park_property/interface/schemas.py`
- `apps/api/tests/test_park_unit.py`
- `apps/api/tests/test_isolation.py`

### 异常处理

- `apps/api/app/core/errors.py`（`AppError`、校验/500 envelope handler）
- `apps/api/app/main.py`（handler 注册）
- `docs/07-engineering-standard/04-exception-standard.md`

### 请求日志

- `apps/api/app/core/logging_config.py`
- `apps/api/app/core/business_logging.py`
- `apps/api/app/core/request_context.py`（`X-Request-Id` 中间件）
- `docs/07-engineering-standard/03-logging-standard.md`

### 审计日志

- `apps/api/app/infrastructure/database/audit.py`（`AuditRecorder`）
- `apps/api/app/infrastructure/database/models/audit.py`
- Park/Unit Service 内同事务 `audit.record(...)`
- `apps/api/tests/test_foundation_compliance.py`（审计相关）

### 配置安全

- `apps/api/app/core/config.py`（生产 JWT/CORS 校验）
- `apps/api/.env.example`
- `apps/api/pyproject.toml`

### 测试

- `apps/api/tests/conftest.py`
- `apps/api/tests/test_health.py`
- `apps/api/tests/test_park_unit.py`
- `apps/api/tests/test_isolation.py`
- `apps/api/tests/test_identity_authorization.py`
- `apps/api/tests/test_foundation_compliance.py`

### 文档 / OpenSpec

- `openspec/config.yaml`
- `openspec/changes/harden-step1-foundation/**`（proposal/design/specs/tasks）
- `docs/06-implementation/phase06-step1-complete.md`
- `docs/06-implementation/phase06-step1-review.md`
- `docs/07-engineering-standard/**`（6 份规范 + README）
- `docs/04-api/openapi-v1-core.yaml`、`docs/04-api/README.md`
- 其它历史分析/设计文档（01–05 目录，非本加固专属但同仓存在）

---

## 4. Alembic revision

| 项 | 值 |
| --- | --- |
| 链 | `<base>` → **`44cb70117ff4`**（step1_identity_park_unit）→ **`8c2f4aa10b7d`**（step1 foundation hardening） |
| **唯一 head** | **是**：`8c2f4aa10b7d (head)` |
| 本机 `alembic current`（对默认 DATABASE_URL） | **`44cb70117ff4`** |

**说明：** 版本图只有一个 head，但当前本地 SQLite 文件的 alembic 版本 **尚未升级到 head**。测试主要依赖 `create_all`/内存库，不依赖该文件是否为最新 revision。运维上属于 **环境未跟 head 的风险**，不是双 head 分叉。

---

## 5. 本次迁移/本地库绝对路径

- 配置默认：`sqlite+pysqlite:///./kwzy_step1.db`（相对 `apps/api` 工作目录）
- 解析到的绝对路径：

**`D:\重构python\kwzy-python\apps\api\kwzy_step1.db`**

（`alembic current` 也是针对该 URL 的 SQLite 文件。）

---

## 6. 是否连接/修改过旧 Java 系统数据库

| 检查 | 结论 |
| --- | --- |
| 默认 `DATABASE_URL` | 本地 SQLite，**不是**旧系统 MySQL |
| 测试 `conftest` | `sqlite+pysqlite:///:memory:`，隔离 |
| 代码路径 | 无引用 `magic` / 旧库连接串作为默认 |
| **验收结论** | **未发现连接或写入旧 Java 系统数据库（`kwzg-Java-main` / 生产 magic 库）的证据** |

---

## 7. 默认管理员 RBAC 种子（无敏感值）

来源：`ensure_default_tenant`（**仅** `APP_ENV in {local, test}` 启动时执行）

| 项 | 内容 |
| --- | --- |
| 租户 | code=`default`，name=`默认租户` |
| 用户 | username=`admin`（密码**不在本报告输出**） |
| 角色 | **ADMIN**（系统管理员） |
| 角色绑定权限 | **`*`（全部权限）** |
| 权限字典种子 | `*`、`park:read`、`park:write`、`unit:read`、`unit:write` |
| 园区范围种子 | **未**默认写入 `user_park_scopes` / `role_park_scopes`；ADMIN 靠 `*` 全园 |

---

## 8. 测试命令与结果（真实执行）

```text
工作目录: D:\重构python\kwzy-python\apps\api
命令:     .\.venv\Scripts\python -m pytest -q --tb=no
环境:     PYTHONPATH=D:\重构python\kwzy-python\apps\api
```

| 指标 | 结果 |
| --- | --- |
| 收集用例 | **23** |
| 通过 | **23 passed** |
| 失败 | 0 |
| 退出码 | **0** |
| Warning | **1**：Starlette `TestClient`/`httpx` 弃用提示 |

---

## 9. OpenSpec validate

```text
openspec validate harden-step1-foundation
→ Change 'harden-step1-foundation' is valid
→ Totals: 1 passed, 0 failed

openspec validate harden-step1-foundation --strict
→ Change 'harden-step1-foundation' is valid

openspec status --change harden-step1-foundation
→ Schema: spec-driven
→ Progress: 4/4 artifacts complete
→ All artifacts complete!

openspec list
→ harden-step1-foundation  ✓ Complete
```

---

## 10. YAML / OpenAPI 校验

| 检查 | 结果 |
| --- | --- |
| 文件 | `docs/04-api/openapi-v1-core.yaml`（约 52906 bytes） |
| PyYAML `safe_load` | **成功** |
| openapi 版本 | **3.1.0** |
| paths 数量 | **37** |
| `openapi_spec_validator` | **未安装**，未做完整 OpenAPI Schema 级校验 |

**结论：** YAML 语法与基本结构 OK；**未做官方 OpenAPI Schema 严格校验**。

---

## 11. 仍存在的 warning / 已知问题 / 未覆盖风险

| 类型 | 内容 |
| --- | --- |
| Warning | pytest：Starlette TestClient 与 httpx 弃用提示 |
| 运维 | 本地 `kwzy_step1.db` 的 alembic **current ≠ head**（停在 `44cb70117ff4`） |
| 审计 | **仅成功写操作**进 `audit_logs`；失败操作不落库（见下节） |
| 授权 | JWT 内嵌 permissions/park_ids，**令牌有效期内不随角色变更即时失效**（设计已承认 ~30m） |
| 开发便利 | non-production 无 Bearer 时仍注入 `tenant_id=1` + `permissions=["*"]`（production 禁止） |
| 日志字段名 | 代码用 `business_module`，规范文档写 `module`（语义一致、字段名不完全对齐） |
| 分层债务 | Application 仍直接构造 ORM 实体 |
| OpenAPI | 与运行时 Step1 路由（尤其 RBAC/审计）可能不完全同步 |
| 未覆盖 | 失败审计、refresh token、权限即时吊销、生产种子关闭策略的 e2e 部署演练、OpenAPI 严格校验、失败操作持久审计 |

### 事务内 AuditRecorder 与失败审计

- **成功路径：** `AuditRecorder.record` 与业务写操作同一 Session，`commit` 时业务与成功审计**同时提交**。  
- **回滚路径：** 业务失败回滚时，**已 flush 的审计也会回滚**。  
- **当前系统是否记录失败操作？**  
  **否。** 未发现独立于业务事务的失败审计写入。  
- **列为后续改进项（本次不实现）：** 失败操作审计（可 outbox/独立 connection/after-commit 策略）。

---

## 12. 安全风险检查（只读）

| 风险项 | 判定 | 说明 |
| --- | --- | --- |
| 默认管理员账号或密码硬编码 | **是（本地种子）** | `bootstrap` 中固定 username；密码哈希由固定明文生成（报告不输出明文）。**仅 local/test 自动执行** |
| 生产自动执行管理员种子 | **否** | `lifespan` 仅 `app_env in {local, test}` 时种子 |
| JWT 仍携带并直接信任权限列表 | **是（有意设计）** | 登录时从 DB 计算后写入 JWT；`deps` 信任 token 内 permissions/park_ids，**不每请求回库** |
| 跨租户角色/权限关联 | **未发现** | 授权查询带 `tenant_id` 过滤 |
| 跨园区访问绕过 | **未发现（主路径）** | 空 park_ids 非全园；`*` 才全园；Repository 强制 scope |
| client_ip 错误信任 X-Forwarded-For | **否（当前不读该头）** | 使用 `request.client.host`；**未**信任 `X-Forwarded-For`（反向代理场景 IP 可能不准，但非“信任伪造头”） |
| 500 泄露堆栈 | **否** | 对外 `INTERNAL_ERROR` 固定文案；堆栈仅服务端 `logger.exception` |
| 审计含密码/Token/敏感参数 | **未见** | `detail` 由业务传入摘要字段；`AuditRecorder` 注释要求非敏感 |

---

## 13. Git（只读）

```text
路径: D:\重构python\kwzy-python
git status  → fatal: not a git repository
git log     → fatal: not a git repository
git diff --stat → 不可用（无 .git）
```

**无法提供有效的 `git diff --stat` / `git status` 变更统计。**  
若需版本化，需在仓库初始化 Git 后由人工提交。

---

## 14. 是否可进入 Party 设计阶段

| 结论 | **可以进入 Party「设计」阶段** |
| --- | --- |
| 前提 | 遵守 `docs/07-engineering-standard/*`；Party 实现前再开独立 OpenSpec/清单 |
| 阻塞项 | **无代码级硬阻塞** |
| 建议先处理（非阻塞） | 本地 DB `alembic upgrade head`；明确失败审计后续 change；JWT 权限快照时效写进 Party 设计假设 |

**不建议在本验收同时开工 Party 编码**；本报告仅批准进入 **Party 设计** 讨论/文档阶段，等待人工确认后再开发。

---

## 最终标识

```text
PHASE06-STEP1-FOUNDATION-ACCEPTANCE-COMPLETE
```

**等待人工确认。**


---

## 后记：close-step1-acceptance-gaps（2026-08-07）

> 历史验收结论「有条件通过」保留；本后记记录缺口关闭结果，**不覆盖上文正文**。

| 原缺口 | 关闭结果 |
| --- | --- |
| alembic current ≠ head | 已升级至 `9f17fd2e9180`（含 `8c2f4aa10b7d` RBAC/audit + `all_parks`） |
| 固定管理员明文密码 | 移除；`LOCAL_ADMIN_PASSWORD`；test fixture；production 禁止种子 |
| `*` 兼全园 | BREAKING：改为 `park_scope_mode` + `roles/users.all_parks` |
| Application 构造 ORM | Park/Unit 改为 Entity+Mapper；架构测试禁止 application 导入 models（bootstrap 白名单） |
| 日志 `business_module` | JSON 输出规范字段 `module`，过渡双写 `business_module` |
| OpenAPI 未严格校验 | `openapi-spec-validator` + 路由一致性测试 |
| 无 Git 保护 | 根目录 `.gitignore` + `step1-git-runbook.md`（不自动 init） |

**pytest：** 35 passed（含授权矩阵与架构/OpenAPI）。  
**文档追踪：** `step1-document-traceability.md` → STEP1-DOCUMENT-TRACEABILITY-COMPLETE  

```text
STEP1-ACCEPTANCE-GAPS-CLOSED
```
