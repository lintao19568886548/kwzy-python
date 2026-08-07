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

**状态：** Accepted  

**上下文：** 一期模型 `parties.park_id` 单园。  

**决策：**

- 一期：Party 归属单园  
- 二期：可引入 `party_parks`，Party 去 park_id  

**后果：** 跨园集团客户一期拆成多 Party 或人工处理。  

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
