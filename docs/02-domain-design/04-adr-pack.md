# ADR 决策包（阶段 05.1 · 架构评审 P0）

> 状态：Accepted  
> 适用范围：kwzy-python v1 主链开发前冻结

---

## ADR-001 — Park / Building / Unit 聚合根边界

**状态：** Accepted  

**上下文：** 领域文档曾把 Building/Unit 写成 Park 内部实体，但二者独立 CRUD 且 Unit 有状态机；合同占用需改 Unit 状态。  

**决策：**

- Park、Building、Unit **均为独立聚合根**  
- 跨聚合只引用 ID  
- 占用/释放仅通过应用服务 `OccupancyService` 编排 Lease + Unit  

**后果：** 禁止 Billing/Investment 直接 UPDATE units。  

---

## ADR-002 — 账单主状态与逾期正交

**状态：** Accepted  

**上下文：** `OVERDUE` 与 `PARTIALLY_PAID` 不能互斥表达「逾期且部分收款」。  

**决策：**

- `status` ∈ {DRAFT, ISSUED, PARTIALLY_PAID, PAID, VOID, DISCARDED}  
- **禁止** status=OVERDUE  
- `is_overdue` = 衍生计算；可选持久化 `overdue_since`  

**后果：** 催缴扫描按 is_overdue；API 返回 is_overdue 字段。  

---

## ADR-003 — Party 园区归属

**状态：** **Superseded**（2026-08-10，由 ADR-003a 取代）  

**原决策（历史保留）：**

- 一期：Party 归属单园（`parties.park_id`）  
- 二期：可引入 `party_parks`，Party 去 park_id  

**原后果：** 跨园集团客户一期拆成多 Party 或人工处理。  

**废止原因：** 人工评审否决单园主档——多园租赁、业主/经纪人/供应商多园服务、同一 `credit_code` 租户内唯一时无法靠复制 Party 解决多园关系。见 **ADR-003a**。

---

## ADR-003a — Party 租户主档 + 多园区关系

**状态：** Accepted（2026-08-10，Phase06-Step2 评审修订；同日二次修订见下）  

**上下文：**  
同一企业可租赁多个园区；产权业主、经纪人、供应商、合作伙伴可服务多园。`credit_code` 在 `tenant_id` 内强唯一后，禁止靠「复制 Party」表达多园。  

**决策：**

1. **Party 主档**仅属 SaaS `tenant_id`，**不**使用单一 `park_id` 表达唯一归属。  
2. 园区关联落在关系表 **`party_park_relations`**（party ↔ park 多对多，通过 `party_role_id` 引用业务角色，见 **ADR-003b**）。  
3. 列表/详情可见性 = 用户 park scope ∩ Party 有效关联园区；`park_scope_mode=ALL` 可见租户内**已有园区关联**的 Party。  
4. **无园区关联**的 Party：仅显式拥有 **`party:manage_unscoped`** 的用户可查询/创建（暂不关联园）/修改/分配首个园区关系。  
   - `all_parks`、`party:read`、`party:write` **均不**自动包含该权限。  
   - 动作权限 `*` 可包含 `party:manage_unscoped` 动作，**仍不得**绕过园区 DataScope 规则。  
5. 禁止为多园重复创建相同企业主档。  
6. 同一 `(tenant_id, party_id, park_id, party_role_id)` 仅允许一条 **ACTIVE** 有效关系（DB + 应用双重保证，见数据库草案）。  

**后果：**

- 原 `docs/03` 基线 `parties.park_id` 与 OpenAPI `Party.park_id` 须在实现前按本 ADR 修订。  
- Lease/Bill 未来可各自带业务 `park_id`，不要求 Party 单园。  
- DataScope 查询须 join/subquery `party_park_relations`。  

**与 ADR-003 关系：** 本 ADR **取代** ADR-003 的一期单园方案；ADR-003 仅作历史记录。

---

## ADR-003b — 园区关系引用 party_role_id（单一角色事实来源）

**状态：** Accepted（2026-08-10，Phase06-Step2 第二轮评审）  

**上下文：**  
若 `party_roles.role_code` 与 `party_park_relations.relation_role` 各存一份角色字符串，将形成**双事实来源**，易不一致且停用角色时无法约束园区关系。  

**决策：**

1. **业务角色唯一落在 `party_roles`**：`role_code` 为首版枚举（PROPERTY_OWNER / LESSEE / BROKER / SUPPLIER / PARTNER / CUSTOMER）。  
2. **`party_park_relations` 使用 `party_role_id` FK** 引用同 tenant、同 party 的 `party_roles.id`；**禁止**再存 `relation_role` 字符串。  
3. 拥有角色 ≠ 已关联任何园区；关联园区必须先有对应 `party_role`。  
4. 停用 `party_role` 前必须检查是否存在有效园区关系；有则业务冲突，须先 end 关系。  
5. Party 业务角色与 Identity RBAC **完全分离**，不授予登录权限。  

**备选否决：** 关系表冗余 `relation_role` — 双写风险。  

**后果：** 创建园区关系 API 入参为 `park_id` + `party_role_id`（或 role_code 经服务解析为 id）；查询通过 join 展示 role_code。

---

## ADR-003c — 个人证件 PII 延后至独立安全能力

**状态：** Accepted（2026-08-10）  

**决策：** Party **首版 migration / API 不创建、不接收、不存储** 证件明文或 ciphertext/hash/masked 列。原因：尚无确认的字段级加密、KMS、轮换与查看脱敏能力。未来须独立 OpenSpec change（KMS、envelope encryption、key_version、轮换、权限）完成后再加字段。Lease/实名 **禁止** 临时明文证件列。

---

## ADR-003d — 生产数据库方言 PostgreSQL 16

**状态：** Accepted（2026-08-10，Party 设计终局）  

**决策：**

1. **生产目标数据库：PostgreSQL 16。**  
2. **SQLite**：仅本地快速开发与单元测试；**不是**生产库；**不是**约束正确性的唯一验证环境。  
3. **不以 MySQL/MariaDB** 作为当前新系统生产目标。  
4. ORM/领域层保持数据库无关；**Alembic 以 PostgreSQL 16 为权威方言**。  
5. Party 实现阶段 **必须** 有 PostgreSQL 集成测试（upgrade/downgrade、唯一索引、外键、并发、审计等，见实施计划）。  
6. SQLite 与 PostgreSQL 行为不一致时，**以 PostgreSQL 16 为准**。  
7. CI 目标：SQLite 快速测试 + PostgreSQL 16 集成测试。  
8. 连接串仅环境变量；源码/文档/测试输出 **不得** 含真实密码。  

---

## ADR-003e — Party 风险事件表与风险权限命名

**状态：** Accepted（2026-08-10）  

**决策：**

1. 首版建立 **`party_risk_events`** 不可变风险历史；`parties.risk_status` 仅存当前状态。  
2. 加入/解除黑名单：同事务更新当前状态 + **追加**风险事件 + 写 `audit_logs`；二者不可互相替代。  
3. 事件 **禁止 UPDATE/DELETE**。  
4. 权限码对齐现有 `module:action` 风格（与 `party:read` / `party:write` / `party:manage_unscoped` 一致）：  
   - **`party:risk_read`** — 读完整风险原因与事件时间线  
   - **`party:risk_manage`** — 执行 blacklist / remove-blacklist  
5. 普通 `party:read` **默认不得**查看完整风险原因。  
6. 不通过普通 PATCH 直接改 `risk_status`。  

**备选否决：** 三节权限码 `party:risk:read`（与现有两段式 `resource:action` 不一致）。

---

## ADR-003f — 旧 /rental/tenant* 移除目标版本

**状态：** Accepted（2026-08-10）  

**决策：**

- `removal_target_version: **v2.0.0**`  
- `removal_gate_status: **NOT_READY**`  
- 到达 v2.0.0 **不**等于可无条件删除；须全部门禁满足 + 独立 OpenSpec change + 人工批准。  
- 弃用期：Deprecation/Sunset 头、调用量指标、适配层调 Party Application Service、禁止 301/302 写、不扩展 rental_tenant。  

---

## ADR-003g — Party 地址独立表 party_addresses

**状态：** Accepted（2026-08-10，implement 预检修订）  

**上下文：**  
早期草案用 Party 主档单一 `address` 字符串，语义模糊（注册/办公/账单混用），无法表达多地址与 primary，且易成为与结构化地址并行的第二事实来源。  

**决策：**

1. 地址落在独立表 **`party_addresses`**（tenant_id、party_id、address_type、行政区划字段、is_primary、status、软删）。  
2. **禁止**在 Party 主档保留含义不清的 `address` 列作为事实来源。  
3. `address_type` 首版：REGISTERED | OFFICE | MAILING | BILLING | OTHER。  
4. 同 Party + 同 type 仅一条有效 primary。  
5. **ORGANIZATION** 首版开放地址 CRUD。  
6. **PERSON** 地址属个人敏感信息：在缺少个人 PII 访问控制前，**不开放地址写入**；不得无权限暴露个人详细地址。  
7. Party 归档不物理删地址历史。  
8. 地址写操作审计；地址明细不进普通业务日志。  

**与旧草案关系：** 显式废止「主档单 address 字段」方案，非静默变更。

---

## ADR-004 — 租户隔离强制点

**状态：** Accepted  

**上下文：** 共享库串租是 P0 事故。  

**决策：**

1. JWT 必须带 `tenant_id`  
2. Repository / 查询基类默认附加 `tenant_id = :current`  
3. 禁止无租户条件的业务 SQL  
4. 集成测试：tenant A 数据对 B 不可见  
5. 超级管理跨租户必须显式 `system` 角色且审计  

**后果：** 阶段 06 第一个基础设施交付物。  

---

## ADR-005 — 园区 DataScope

**状态：** Accepted（**2026-08-07 修订**：动作权限与全园范围分离）  

**决策：**

- 有效园区 = role_park_scopes ∪ user_park_scopes（默认并集）  
- 写操作必须校验 park_id ∈ scope  
- 列表查询强制 park 过滤或 scope IN  
- **动作权限**（`permissions`，含 `*` 表示全部动作）与**园区数据范围**正交，互不推导  
- **全园区访问**仅由显式标记表达：`roles.all_parks` / `users.all_parks`（解析为 `park_scope_mode=ALL`）  
- **禁止**用 `permissions` 含 `*` 或 `is_platform_admin` 绕过园区 scope  
- `park_scope_mode`：`NONE` | `LIST` | `ALL`；空 `park_ids` 且非 ALL → 拒绝，**绝不**表示全园  

**修订原因（close-step1-acceptance-gaps）：**  
原表述「`permissions` 含 `*` 可绕过园区」将功能权限与数据权限耦合，与旧系统「菜单权限 + 园区授权」双通道及工程规范冲突；验收有条件通过后以 BREAKING 方式收紧。  

---

## ADR-006 — 模块分层模板

**状态：** Accepted  

**决策：** 每个业务模块允许两种落地深度，但依赖方向固定：

```text
interface (api, schemas)
  → application (service)
    → domain (纯规则/状态机，可选薄)
    → infrastructure (ORM models, repository, adapters)
```

**禁止：** domain 依赖 FastAPI/SQLAlchemy；跨模块 import ORM 写库。  

**一期最小文件集：**

```text
api.py / schemas.py / service.py / models.py / repository.py / domain.py(可选)
```

---

## ADR-007 — 高敏操作二次验证（page-access）

**状态：** Accepted  

**上下文：** 催缴短信误发风险；旧系统有 page-access。  

**决策：**

1. `POST /auth/page-access/send` 发送验证码（绑定 user+purpose）  
2. `POST /auth/page-access/verify` 换取短期 `page_access_proof`  
3. `POST /collection/sms/send` **必须**携带未使用且未过期的 proof  
4. proof 存 `page_access_proofs`（hash），一次性  

**purpose 一期：** `COLLECTION_SMS`  

---

## ADR-008 — Payment 产品语义

**状态：** Accepted  

**决策：**

- 统一中文：**收款登记**  
- 英文资源名可保留 `payments`（业界习惯）  
- OpenAPI description 必须写明非在线支付订单  
- 在线支付 / 回调 / 租户收银台 = **Out of Scope v1**  

---

## ADR-009 — 独立库密钥

**状态：** Accepted  

**决策：** `tenants.dedicated_secret_ref` 仅存引用 ID；真实连接串在密钥管理系统。删除 `dedicated_dsn` 明文列。  

---

## ADR-010 — used_area 投影

**状态：** Accepted  

**决策：** 见领域文档；源=有效 `lease_contract_units`；OccupancyService 回写。  

---

## ADR-011 — 合同条款与附件

**状态：** Accepted  

**决策：**

- 条款：`lease_terms` 表  
- 附件：通用 `attachments` + `StoragePort`  
- 合同头 `increase_date/rate` 可作为主递增缓存，以 terms 为准  

---

## ADR-T01 — 任务队列

**状态：** Accepted  

**决策：** 一期 Redis + 进程内/独立 worker；导入/AI 强制异步 Job。量大再 Celery。  

---

## ADR-T02 — 对象存储

**状态：** Accepted  

**决策：** `StoragePort` 接口；本地目录实现默认；S3/OSS 可替换。附件表只存 key。  

---

## ADR-T03 — 短信

**状态：** Accepted  

**决策：** `SmsSender` 端口；local 用 Mock；生产接供应商。验证码存 Redis。  

---

## ADR-T04 — 时区

**状态：** Accepted  

**决策：** 数据库时间戳 UTC；业务日（due_date、账期）按租户时区默认 `Asia/Shanghai` 的日历日。  

---

## ADR-T05 — 事务与 Outbox

**状态：** Accepted  

**决策：** 单模块本地事务；跨上下文副作用写 `outbox_events` 同事务；消费方 `inbox_consume_log` 幂等。一期可同步调用邻模块应用服务 + 写 outbox 备查。  

---

## ADR-T06 — 幂等

**状态：** Accepted  

**决策：** 写接口支持头 `Idempotency-Key`；表 `idempotency_keys`。至少：`payments` 创建、`bills/{id}/issue`。  

---

## ADR-T07 — 生产关闭开发免登

**状态：** Accepted  

**决策：** `app_env=production` 时禁止 mock CurrentUser；无 Bearer 一律 401。  
