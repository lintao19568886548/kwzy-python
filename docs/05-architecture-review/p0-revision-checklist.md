# P0 设计修订验收清单（阶段 05.1）

> 全部勾选后方可进入阶段 06 编码

| ID | 问题 | 修订落点 | 状态 |
| --- | --- | --- | --- |
| P0-1 | Bill OVERDUE 与部分收款冲突 | `02-aggregates` 状态机；DDL `status`/`overdue_since`；OpenAPI `is_overdue` enum | ✅ |
| P0-2 | LeaseTerm/Attachment 与 DDL 不一致 | `lease_terms` + `attachments` 表；领域说明 | ✅ |
| P0-3 | OpenAPI envelope/命名 | snake_case path；ApiEnvelopeOk/ErrorResponse；描述 | ✅ |
| P0-4 | Party API 不完整 | OpenAPI GET/PATCH `/parties/{party_id}` | ✅ |
| P0-5 | 租户/园区过滤规范 | ADR-004 / ADR-005 | ✅ |
| P0-6 | 分层未冻结 | ADR-006 + api README | ✅ |
| P0-7 | 催缴二次验证 + 案件闭环 | ADR-007；`collection_cases`/`collection_records`；page-access API | ✅ |
| P0-8 | 支付语义 + 分摊核销 | ADR-008；Payment + `payment_allocations`；部分收款 | ✅ |
| P0-9 | dedicated_dsn 明文 | `dedicated_secret_ref`；ADR-009 | ✅ |
| P0-10 | used_area 双写 | ADR-010；领域投影规则；DDL 注释 | ✅ |

**附加交付：**

| 项 | 路径 | 状态 |
| --- | --- | --- |
| ADR 包 | `docs/02-domain-design/04-adr-pack.md` | ✅ |
| 范围一页纸 | `docs/02-domain-design/05-phase06-scope.md` | ✅ |
| DDL v1.1 patch | `docs/03-database/01-core-ddl-v1.1-patch.sql` | ✅ |
| Building API | OpenAPI `/buildings/{building_id}` | ✅ |

---

## 复检签署

| 角色 | 结果 | 日期 |
| --- | --- | --- |
| 架构（本文档自动修订） | P0 设计项已闭合 | 05.1 |
| 进入 06 批准 | 待产品/负责人确认本清单 | — |

闭合后可使用：

```text
【P0 DESIGN REVISION COMPLETE】
允许进入阶段 06（SQLAlchemy + Alembic + 核心 CRUD）
范围以 05-phase06-scope.md 为准
```
