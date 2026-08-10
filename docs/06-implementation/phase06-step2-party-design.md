# Phase06-Step2 Party 设计记录（终稿）

> 状态：**FINAL APPROVAL READY**  
> 分支：`design/party-domain-v1`  
> OpenSpec：`design-party-domain`  
> 日期：2026-08-10  

---

## 1. 范围

仅设计/ADR/OpenSpec/草案。  
**不** apply、编码、迁移、commit、push、创建 implement change。

---

## 2. 终局决策摘要

| 项 | 结论 |
| --- | --- |
| 生产库 | **PostgreSQL 16** |
| SQLite | 开发 + 单元测试 only |
| 风险历史 | 首版 **party_risk_events** |
| 风险权限 | party:risk_read / party:risk_manage |
| 旧接口 | 目标 **v2.0.0**，gate **NOT_READY** |

---

## 3. 测试分工

### 3.1 SQLite（快速）

- 领域规则、service 逻辑、大量 API 用例  
- **不得**单独作为生产约束通过依据  

### 3.2 PostgreSQL 16 集成测试（权威，Party 实现必含）

至少：

1. Alembic base → head  
2. downgrade → upgrade  
3. tenant_id 隔离  
4. credit_code 非空唯一  
5. ACTIVE 园区关系部分唯一索引  
6. 外键约束  
7. 并发创建重复 Party（credit_code）  
8. 并发创建重复有效园区关系  
9. 软删除与恢复  
10. 事务审计（含 risk 事件 + audit_logs 同事务）  

连接串仅环境变量；无真实密码入仓。

### 3.3 CI 目标

- Job A：SQLite 快速测试  
- Job B：PostgreSQL 16 集成测试  

---

## 4. 实现分期（批准后另开 change）

| 阶段 | 内容 |
| --- | --- |
| I0 | PG 测试容器/CI 骨架 |
| I1 | Alembic（PG 权威）parties/roles/relations/contacts/risk_events |
| I2 | Domain/Repo 可见性 + unscoped |
| I3 | risk 动作 + 事件 + 审计同事务 |
| I4 | roles/relations/contacts API |
| I5 | archive/restore |
| I6 | legacy adapter + metrics + OpenAPI |
| 不做 | 证件列、旧接口删除、Lease 规则、旧库 ETL |

### 建议 implement change 名称

**`implement-party-master`**

（可选后续：`implement-party-legacy-adapter`、`implement-party-pii-identity`、`remove-legacy-rental-tenant-v2`）

---

## 5. 是否具备最终批准条件

| 项 | 结论 |
| --- | --- |
| 结构性 Open Questions | **无** |
| 设计完整性 | **具备最终人工批准条件** |
| 编码 | **否**，待批准 + 新 open implement change |

---

```text
PHASE06-PARTY-DESIGN-FINAL-APPROVAL-READY
```
