# Party 领域设计 v1（Phase06-Step2 终稿）

> 状态：**FINAL APPROVAL READY**  
> 分支：`design/party-domain-v1`  
> OpenSpec：`design-party-domain`  
> 终局修订：2026-08-10  
> **禁止本阶段**：业务代码、ORM、迁移、Repository、Router、apply、commit、push、创建 implement change  

---

## 1. 决策追踪表

| 决策 | 采用方案 | 原因 | 影响文档 | 影响模块 |
| --- | --- | --- | --- | --- |
| 生产方言 | **PostgreSQL 16** | 生产权威；部分唯一索引与约束 | ADR-003d、DDL、实施计划 | 全栈/Party 实现 |
| SQLite | 本地开发 + 单测 only | 快速反馈；非约束权威 | ADR-003d | tests |
| 未关联园权限 | `party:manage_unscoped` | 租户级草稿主体 | API、OpenSpec | party |
| 主档与园 | 无 park_id；`party_park_relations.party_role_id` | 多园 + 角色单一来源 | ADR-003a/b | party |
| 生命周期/风险 | status + risk_status | 可 ACTIVE 且黑名单 | 领域、DDL | party |
| 风险历史 | **首版 `party_risk_events`** | 不可变业务时间线 | ADR-003e、DDL、API | party |
| 风险权限 | `party:risk_read` / `party:risk_manage` | 与现有 `party:*` 两段式一致 | ADR-003e | party |
| credit_code | 非空 tenant 唯一（含 ARCHIVED） | 防重复主档 | DDL | party |
| 证件 | 首版零字段 | 无加密设施 | ADR-003c | 未来 PII |
| 归档 | archive/restore；默认排除 ARCHIVED | 软删 | API | party |
| contacts | 嵌套 REST + 软删 | 归属与脱敏 | API | party |
| 旧接口 | 目标 **v2.0.0**；gate **NOT_READY** | 兼容下线 | ADR-003f | adapter |
| 模块 | `app/modules/party/` | 已确认 | 实施计划 | party |

---

## 2. 已决策事项 / 非阻塞参数 / 结构性问题

### 2.1 已决策事项（无 Open Question）

- PostgreSQL 16 生产；SQLite 开发/单测  
- 非 MySQL 生产目标  
- party:manage_unscoped  
- party_role_id 单一角色来源  
- 证件首版排除  
- party_risk_events 首版必建  
- party:risk_read / party:risk_manage  
- 旧接口目标 v2.0.0 + 门禁 + NOT_READY  
- ACTIVE 关系部分唯一索引（PG 权威）  

### 2.2 非阻塞实施参数（实现 change 内选定，不阻塞最终批准）

- 本地 PG 容器镜像标签精确 patch 版本（如 16.x）  
- CI 中 PG service 资源规格  
- Sunset 响应头具体日期字符串格式  
- blacklist 事件 `source` 枚举扩展值（首版：API / ADAPTER / SYSTEM）  

### 2.3 结构性 Open Questions

**无。** 不再保留阻塞设计的结构性开放问题。

---

## 3. 权限一览

| 码 | 含义 |
| --- | --- |
| party:read | 读 park-scope 可见 Party（不含完整风险原因默认） |
| party:write | 写主档/角色/关系/联系人/归档恢复（非风险状态专用） |
| party:manage_unscoped | 零园区关联 Party |
| **party:risk_read** | 读风险事件与完整 reason |
| **party:risk_manage** | blacklist / remove-blacklist |
| * | 全部动作；仍不绕过 park scope |

---

## 4. 风险状态与事件

### 4.1 当前状态（parties）

- `risk_status`: NORMAL | BLACKLISTED  
- 便捷查询字段；**不是**完整历史  

### 4.2 party_risk_events（不可变）

| 字段 | 说明 |
| --- | --- |
| tenant_id, party_id | 必填 |
| event_type | BLACKLISTED \| BLACKLIST_REMOVED |
| previous_risk_status, new_risk_status | 变更前后 |
| reason | **必填**（加入与解除均必填） |
| operator_user_id | 操作者 |
| request_id | 关联请求 |
| source | API / ADAPTER / SYSTEM 等 |
| occurred_at, created_at | 时间 |

规则：

1. 每次加入/解除 **追加** 事件，禁止 UPDATE/DELETE 事件行。  
2. 状态变更 + 事件 + **audit_logs** 同事务。  
3. audit_logs ≠ party_risk_events（系统审计 vs 业务风险史）。  
4. ARCHIVED Party 历史事件保留；restore **不**自动解除黑名单。  
5. Lease 是否禁签：仅预留 risk_status，本阶段不实现。  

---

## 5. 数据库方言策略

| 环境 | 方言 | 用途 |
| --- | --- | --- |
| 生产 | **PostgreSQL 16** | 权威约束与行为 |
| 本地/单测 | SQLite | 快速反馈 |
| 集成测 | PostgreSQL 16 | 约束/并发/Alembic 权威验证 |

不一致时以 **PostgreSQL 16** 为准。ACTIVE 关系唯一索引以 PG partial unique 为规范 DDL。

---

## 6. 旧接口

- 旧：`/rental/tenant*` → 适配层 → Party Application Service  
- 新：`/api/v1/parties*`  
- `removal_target_version: v2.0.0`  
- `removal_gate_status: NOT_READY`  
- 门禁见实施计划；未满足前即使版本到 2.0.0 仍保留兼容层  

---

## 7. 关联交付

- ADR：`04-adr-pack.md`（003a–003f）  
- DDL：`docs/03-database/03-party-ddl-draft-v1.sql`  
- API：`docs/04-api/party-api-draft-v1.md`  
- 计划：`docs/06-implementation/phase06-step2-party-design.md`  
- OpenSpec：`openspec/changes/design-party-domain/`  
