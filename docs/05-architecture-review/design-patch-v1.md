# Design Patch v1（架构评审 P0 闭合包）

> 版本：v1  
> 阶段：05.1  
> 范围：**只改设计**（领域 / DDL / OpenAPI / ADR），**不生成 SQLAlchemy / CRUD 业务代码**  
> 状态：✅ 已落地，等待阶段 06

---

## 0. 修订目标对照

| # | 要求 | 状态 | 主要落点 |
| --- | --- | --- | --- |
| 1 | 分离逾期与支付状态；支持部分收款 | ✅ | 领域状态机 + DDL + OpenAPI |
| 2 | LeaseTerm / Attachment 与 DDL 一致 | ✅ | 基线表 `lease_terms` / `attachments` |
| 3 | OpenAPI snake_case + response envelope | ✅ | `openapi-v1-core.yaml` v1.1 |
| 4 | Party GET/PATCH API 设计 | ✅ | OpenAPI `/parties/{party_id}` |
| 5 | Repository 租户/园区过滤基类设计 | ✅ | `06-repository-and-layering.md` |
| 6 | 冻结 domain/application/infrastructure/interface | ✅ | 同上 + ADR-006 |
| 7 | 催缴闭环 collection_case + collection_record | ✅ | 领域 + `collection_records` + API |
| 8 | Payment=收款登记 + payment_allocation 分摊核销 | ✅ | 领域 + DDL + OpenAPI |

---

## 1. Bill：逾期状态 ⊥ 支付状态 + 部分收款

### 1.1 支付/收付主状态（`bills.status`，互斥）

```text
DRAFT → ISSUED → PARTIALLY_PAID → PAID
         ↓
        VOID
DRAFT → DISCARDED
```

| 状态 | 含义 |
| --- | --- |
| ISSUED | 已签发，核销额=0 |
| PARTIALLY_PAID | 0 < paid_amount < total_amount |
| PAID | 已结清 |

**禁止** `status = OVERDUE`。

### 1.2 逾期（正交衍生）

```text
is_overdue =
  status ∈ {ISSUED, PARTIALLY_PAID}
  AND due_date < today
  AND (total_amount - paid_amount) > 0
```

- 可选落库：`overdue_since`  
- 列表筛选：`is_overdue=true`（非改 status）  

### 1.3 部分收款

```text
Payment (收款登记)
  └── PaymentAllocation[]  →  多账单 / 部分金额
        └── 回写 bill.paid_amount
        └── 重算 bill.status ∈ {ISSUED, PARTIALLY_PAID, PAID}
```

同一账单可对应 **多笔** Payment / Allocation。

**文档：**  
`docs/02-domain-design/02-aggregates-and-state-machines.md` §3–4  
`docs/02-domain-design/04-adr-pack.md` ADR-002 / ADR-008  

---

## 2. LeaseTerm / Attachment 一致性

| 领域概念 | DDL 表 | 说明 |
| --- | --- | --- |
| LeaseTerm | `lease_terms` | term_type: INCREASE / RENT_FREE / OTHER |
| Attachment | `attachments` | resource_type + resource_id + storage_key |

- 已写入 **`01-core-ddl-v1.sql` 基线**（不再仅存在 patch）  
- 合同头 `increase_date/rate` 可作为主递增缓存，**以 terms 为准**（ADR-011）  

---

## 3. OpenAPI 规范统一

| 规范 | 约定 |
| --- | --- |
| 命名 | 路径/query/body **snake_case**（`park_id`, `bill_id`…） |
| 成功响应 | `{ "code": "OK", "message": "...", "data": ... }` |
| 错误响应 | `ErrorResponse` 同 envelope |
| 版本 | OpenAPI **1.1.0** |

**文件：** `docs/04-api/openapi-v1-core.yaml`、`docs/04-api/README.md`

---

## 4. Party API 补齐

| 方法 | 路径 | operationId |
| --- | --- | --- |
| GET | `/parties` | listParties |
| POST | `/parties` | createParty |
| GET | `/parties/{party_id}` | getParty |
| PATCH | `/parties/{party_id}` | updateParty |

---

## 5. Repository 租户/园区过滤基类（设计）

**文件：** `docs/02-domain-design/06-repository-and-layering.md`

摘要：

- 抽象 `TenantParkRepositoryBase`  
  - `apply_tenant(query)` 强制 `tenant_id`  
  - `assert_park_in_scope` / `apply_park_scope`  
  - `get_by_id_for_tenant` 双条件  
- 业务仓储继承该基类  
- Application 禁止绕过仓储裸 SQL  
- 阶段 06 用测试锁死串租/越园  

**本阶段不写 SQLAlchemy 实现。**

---

## 6. 分层冻结

```text
interface      →  api / schemas
application    →  service / use-case
domain         →  entities / states / events
infrastructure →  models / repository / adapters
```

依赖单向；domain 不依赖框架。见 ADR-006 与 `06-repository-and-layering.md`。

---

## 7. 催缴闭环

```text
is_overdue 账单
    → collection_cases（案件）
        → collection_records（跟进记录：SMS/CALL/VISIT/NOTE/SYSTEM）
    → 结清 PAID → case CLOSED
```

| 表 | 职责 |
| --- | --- |
| `collection_cases` | 案件头：状态、级别、跟进人、欠款快照 |
| `collection_records` | 跟进流水（**冻结名**；替代 collection_actions） |

| API | 说明 |
| --- | --- |
| `POST/GET /collection/cases` | 建案/列表 |
| `GET/PATCH /collection/cases/{case_id}` | 详情/改状态 |
| `GET/POST /collection/cases/{case_id}/records` | 记录 |
| `POST /collection/sms/preview|send` | 短信；send 需 page_access_proof |

---

## 8. Payment 语义 + 分摊核销

| 概念 | 定义 |
| --- | --- |
| **Payment** | **收款登记**（运营确认已收到的钱），**不是**在线支付订单 |
| **payment_allocations** | 将一笔收款分摊到一张或多张账单的核销行 |

约束：

1. sum(allocations.amount) ≤ payment.amount  
2. 单账单累计核销 ≤ total_amount  
3. method 可含 WECHAT/ALIPAY 表示渠道备注；**网关/回调/租户收银台 = 二期**  

---

## 9. 文档变更清单

### 新增

| 路径 |
| --- |
| `docs/05-architecture-review/design-patch-v1.md`（本文） |
| `docs/02-domain-design/06-repository-and-layering.md` |
| （既有）`04-adr-pack.md` / `05-phase06-scope.md` / `p0-revision-checklist.md` |

### 修改

| 路径 | 变更要点 |
| --- | --- |
| `docs/02-domain-design/02-aggregates-and-state-machines.md` | Bill 状态、Payment、CollectionRecord 闭环 |
| `docs/02-domain-design/01-domain-overview.md` | 术语与 ADR 摘要 |
| `docs/03-database/01-core-ddl-v1.sql` | overdue_since、lease_terms、attachments、collection_records… |
| `docs/03-database/01-core-ddl-v1.1-patch.sql` | 与基线对齐说明 / 重命名注释 |
| `docs/03-database/02-schema-notes.md` | 表职责与逾期规则 |
| `docs/04-api/openapi-v1-core.yaml` | v1.1 全套契约 |
| `docs/04-api/README.md` | 规范说明 |
| `apps/api/README.md` | 分层约定（仍无业务实现） |

---

## 10. 明确不做（本 patch）

- ❌ SQLAlchemy models / Alembic 迁移脚本业务实现  
- ❌ 业务 CRUD 代码  
- ❌ 前端页面  
- ❌ 在线支付、雷达、门禁等二期域  

---

## 11. 出口状态

```text
【DESIGN PATCH v1 COMPLETE】

8 项设计修订均已落入 domain / database / api 文档。
未生成 SQLAlchemy 业务代码。
等待下一阶段：阶段 06（按 05-phase06-scope.md 实现）。
```

---

## 12. 阶段 06 入口条件（提醒）

1. 以本 patch + ADR 包为准  
2. 先落地 `TenantParkRepositoryBase` + 租户隔离测试  
3. 再 Park → Party/Lease → Bill → Payment → Collection  
4. Bill 永远不要写入 `OVERDUE` 状态值  
