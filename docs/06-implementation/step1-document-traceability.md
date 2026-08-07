# Step1 文档使用追踪表（close-step1-acceptance-gaps 实施前）

> 生成时间：2026-08-07  
> 关联 OpenSpec：`openspec/changes/close-step1-acceptance-gaps`  
> 目的：代码/库/API/架构/文档一致性检查；**本文件生成时未修改业务代码、未执行迁移**  
> 结论摘要：见文末「冲突结论」

---

## 变更范围回顾（OpenSpec 已批准方向）

| 主题 | OpenSpec 既定方向 |
| --- | --- |
| DB | 仅新系统 SQLite 升至 head `8c2f4aa10b7d`；备份/回滚 |
| 密码 | 移除源码固定管理员明文；local env；test fixture |
| 授权 | `*` 仅动作权限；全园独立表达；空范围拒绝 |
| 分层 | Application 不构造 ORM；Entity+Mapper |
| 日志/OpenAPI | `module` 字段；OpenAPI 3.1 严格校验 |
| Git | 仅 runbook，不自动 init |

---

## 追踪表

| 文档路径 | 是否读取 | 与本次变更的关系 | 采用的设计/规则 | 发现的冲突 | 是否需要更新 |
| --- | --- | --- | --- | --- | --- |
| **01-old-system-analysis/** | | | | | |
| `01-project-structure.md` | 是 | 背景：旧 monorepo、中心库+租户库、/api | 新系统默认共享库+tenant_id；不连旧库 | 无 | 否（只读依据） |
| `02-backend-business-analysis.md` | 是 | 旧 RBAC=菜单+权限码+园区；登录中心库 | 新：租户内 RBAC+JWT；园区 user∪role 并集 | 旧双通道(role_park/user_park)与新并集兼容 | 否 |
| `03-database-analysis.md` | 是 | 旧 user/role/role_park/user_park | 新表 permissions/user_roles/role_park_scopes/audit_logs | 旧无独立 permission 字典；新更细，非破坏旧语义 | 否 |
| `04-frontend-page-analysis.md` | 是 | 登录/园区页面入口 | 不影响前端页面结构 | 无 | 否 |
| `05-api-analysis.md` | 是 | 旧 /auth/* /park/* 路径量级 | Step1 保持 /api/v1 auth/parks/units | 无阻塞 | 否（全量旧 API 对照远期） |
| `06-business-process-analysis.md` | 是 | 登录拿菜单权限码流程 | 登录仍发 token+permissions | 旧无「* 即全园」明文；新曾错误实现 | 否 |
| `07-system-problem-analysis.md` | 是 | 权限交织、分层债 | 本 change 正针对授权分离与分层 | 无 | 否 |
| `08-python-rebuild-suggestion.md` | 是 | 功能权限 vs 数据权限三分 | **采用**：功能权限与园区数据权限分离 | 若文档仍写 * 兼全园需改 | **是**（apply 时核对 * 语义） |
| **02-domain-design/** | | | | | |
| `01-domain-overview.md` | 是 | IdentityAccess/ParkProperty 边界；§5.2 园区范围 | **采用**：有效园区=角色∪用户并集；超管显式标记+审计 | 「超级管理员可跨园」未写清与 `*` 关系 | **是**（补充 all_parks 语义） |
| `02-aggregates-and-state-machines.md` | 是 | Park/Unit 状态机；used_area 投影 | **采用**：Unit 状态迁移；不改合同/账单语义 | 无 | 否（本 change 不改聚合业务含义） |
| `03-context-map.md` | 是 | Identity ACL → 各模块 | **采用**：鉴权横切 | 无 | 否 |
| `04-adr-pack.md` | 是 | ADR-004/005/006 租户、园区、分层 | **采用** ADR-004 tenant 强制、ADR-006 分层 | **ADR-005 写明 `permissions` 含 `*` 可绕过园区 scope** — 与本 change **BREAKING 修正**冲突 | **是（必须修订 ADR-005）** |
| `05-phase06-scope.md` | 是 | Step1 范围 Identity+Park+Unit | **采用**：本 change 仍不扩 Party | 无 | 否 |
| `06-repository-and-layering.md` | 是 | Repository 基类、TenantContext 伪代码 | **采用**：tenant 过滤+park scope；禁止 application 裸 SQL | 伪代码写「空 park_ids+超级权限另议」——需与 all_parks 对齐 | **是** |
| `README.md` | 是 | 索引 | — | 无 | 可选更新索引 |
| **03-database/** | | | | | |
| `01-core-ddl-v1.sql` | 是 | 基线 DDL：tenants/users/roles/permissions/role_park/user_park/parks/units/audit_logs | **采用** 表名与字段主语义 | **缺 `all_parks` 列**（拟增）；Alembic hardening 表与文档基线可能不同步细节 | **是**（同步 RBAC/audit/all_parks） |
| `01-core-ddl-v1.1-patch.sql` | 是 | 增量补丁说明 | 本 change 可能再加 migration | 与 live alembic 双轨需说明 | **是**（注明以 Alembic 为准） |
| `02-schema-notes.md` | 是 | 原则、audit_logs 说明 | **采用** audit 同事务、非敏感 detail | 未写 all_parks；permissions 全局字典 | **是** |
| **04-api/** | | | | | |
| `openapi-v1-core.yaml` | 是 | 契约；login 含 tenant_code | **采用** snake_case、envelope、tenant_code | 可能缺 park_scope 字段、RBAC 权限码说明、与运行时权限依赖不完全一致 | **是**（非破坏性同步） |
| `README.md` | 是 | v1.1 要点 | envelope/snake_case | 授权语义需补充 | **是** |
| **05-architecture-review/** | | | | | |
| `domain-review.md` | 是 | 聚合边界、权限问题 | **采用** 主链可冻结；避免再引入耦合 | 无阻塞 | 否（历史评审保留） |
| `database-review.md` | 是 | 多租户/权限 DDL 缺口 | 推动 RBAC/audit 落地 | 已部分关闭 | apply 后可标注关闭项 |
| `api-review.md` | 是 | API 一致性 | envelope、OpenAPI | 严格校验仍缺 | apply 完成 OpenAPI 任务 |
| `technical-review.md` | 是 | 分层、基础设施 | **采用** 禁止 Router 碰 DB | Application 构造 ORM 仍为债 | 本 change 目标关闭 |
| `design-patch-v1.md` | 是 | P0 闭合与 ADR 引用 | **采用** 分层、scope 基线 | 若写 * 兼全园需修订 | **检查后按需** |
| `final-report.md` | 是 | 条件通过与 P0 | 历史裁定 | 验收后状态已演进 | **是**（追加后记，不静默改历史） |
| `p0-revision-checklist.md` | 是 | P0 勾选 | 已完成项保持 | 无 | 可选后记 |
| `README.md` | 是 | 索引 | — | 无 | 可选 |
| **06-implementation/** | | | | | |
| `phase06-step1-complete.md` | 是 | Step1 交付 | Identity+Park+Unit 范围 | 过时「* 全园」描述若有 | **是** |
| `phase06-step1-review.md` | 是 | 审查结论与修复 | **采用** 空 park_ids≠全园；tenant 强制 | 当时仍 * 全园 | **是**（记录模型变更原因） |
| `phase06-step1-foundation-acceptance-report.md` | 是 | 有条件通过；gap 列表 | **本 change 直接针对该报告缺口** | current≠head；固定密码；* 全园；ORM 分层；日志字段 | **是**（关闭缺口后更新状态） |
| `step1-document-traceability.md` | 本文件 | 追踪 | — | — | 本文件 |
| **07-engineering-standard/** | | | | | |
| `01-architecture-standard.md` | 是 | **强制**四层；禁 Application 当领域扛 ORM 规则 | **全部采用**；本 change 分层整改依据 | Application 直接构造 ORM **违反**本规范（已知，待修） | 否（规范正确，代码改） |
| `02-code-comment-standard.md` | 是 | 中文 docstring | apply 时新/改代码遵守 | 无 | 否 |
| `03-logging-standard.md` | 是 | 强制 `module` 字段 | **采用 module** | 代码现用 `business_module` | **是**（代码改+可双写） |
| `04-exception-standard.md` | 是 | envelope、AppError | **采用**；保持现有 handler | 无阻塞 | 否 |
| `05-testing-standard.md` | 是 | 隔离/权限测试矩阵 | **采用** 三类测试+隔离 | 写「permissions=["*"] 可跨园」与新授权模型冲突 | **是（必须修订）** |
| `06-development-checklist.md` | 是 | 模块交付门禁 | **采用** | 「超管仅 * / platform_admin」需改为 * + all_parks | **是** |
| `README.md` | 是 | 索引 | — | 无 | 否 |

---

## 冲突与一致性结论

### A. 阻塞级冲突（会停止 apply）

| # | 规则触发 | 判定 |
| --- | --- | --- |
| 1 | 旧系统分析 vs 领域业务含义 | **无**。旧系统本就是「功能权限 + 园区数据范围」双通道；分离 * 与全园是纠正错误实现，不否定旧业务。 |
| 2 | 领域 vs DDL | **无阻塞**。拟增 `all_parks` 属扩展，apply 时同步 DDL 文档与 migration。 |
| 3 | ORM/Alembic vs 库文档 | **有差距、非阻塞**。`02-schema-notes`/基线 SQL 与 live migration 需同步说明「以 Alembic 为运行真相」；不阻止按 design 执行 upgrade。 |
| 4 | 运行时路由 vs OpenAPI 破坏性冲突 | **无破坏性**。路径仍 /auth、/parks、/units；可能增可选 claim/字段。任务要求非破坏性 OpenAPI 同步。 |
| 5 | 架构评审 vs Mapper 方案 | **无冲突**。评审与 07 规范均要求 Application 不扛 ORM 业务；Mapper 正是关闭已记录债务。 |
| 6 | 工程规范 vs 现有设计无法两全 | **可调和**：07 要求分层正确；02 ADR-005 的「* 绕过园区」与 07-testing 的「* 可跨园」是**过时约定**，OpenSpec design 已明确 **BREAKING 修正**。处理方式：**apply 时显式修订 ADR-005 与 07 相关条目**，不得静默改 Identity/Park/Unit 业务聚合含义。 |
| 7 | 改动改变 Identity/Park/Unit 业务含义 | **Park/Unit 聚合业务含义不变**（创建/改/状态/软删）。**Identity 授权语义变严（BREAKING）**：仅 * 不再全园——属验收批准的目标变更，需在实现说明与种子迁移中显式处理。 |

### B. 必须在 apply 中处理的文档债务（非停止）

1. **修订 ADR-005**：删除「permissions 含 * 可绕过园区」；改为 all_parks / park_scope_mode。  
2. **修订 `07/.../05-testing-standard.md` 与 `06-development-checklist.md`** 中超管判定。  
3. **同步 `03-database`**：RBAC 现状、audit、拟议 all_parks、Alembic 为权威。  
4. **同步 `04-api`**：权限与 scope 说明、严格校验。  
5. **更新 `06-implementation` 完成/验收报告后记**（保留历史，追加变更原因）。  
6. **对齐 `02/.../01-domain-overview` §5.2 与 06-repository 伪代码**。  

### C. 仅报告、不静默改领域含义的项

- Party/Lease/Bill 设计保持 02 文档；本 change 不实现。  
- 失败审计仍不落库：与 foundation-compliance 一致，列为剩余风险。  

---

## 采用结论摘要（写入实现约束）

| 来源 | 采用结论 |
| --- | --- |
| 01 旧系统 | 功能权限与园区授权本应分离；中心/租户模型启发 tenant_id |
| 02 领域 | Park/Unit 独立聚合；Repository 租户+园区过滤；ADR-004 强制 tenant |
| 03 库 | tenant_id 行隔离；permissions 字典；audit_logs；迁移以 Alembic 为准 |
| 04 API | envelope；snake_case；login tenant_code |
| 05 评审 | 关闭 Application 构造 ORM、加固隔离测试 |
| 06 实施/验收 | 关闭 current≠head、固定密码、* 全园、日志字段 |
| 07 工程规范 | 四层强制；module 日志字段；异常 envelope；测试矩阵 |

---

## 是否允许继续 OpenSpec apply

| 判定 | 说明 |
| --- | --- |
| **无阻塞级业务冲突** | 可继续 apply |
| **前提** | apply 时必须同步修订 ADR-005 与 07 中「* = 全园」表述；迁移仅限新系统 SQLite |
| **若人工不同意 BREAKING 授权语义** | 停止，不得实现 * 与园区分离 |

---

## 标识

```text
STEP1-DOCUMENT-TRACEABILITY-COMPLETE
```

**下一步（无阻塞时）：** 执行 `close-step1-acceptance-gaps` 的 OpenSpec apply（实现 tasks）。  
**若人工对 ADR-005 修订或 BREAKING 授权有异议：** 先确认再 apply。
