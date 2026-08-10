## Context

Party 设计终局三项决策已并入。设计 only。

## Goals / Non-Goals

**Goals:** 冻结 PG 16 生产方言、party_risk_events、v2.0.0 下线目标；无结构性 Open Questions。  

**Non-Goals:** apply、编码、迁移、commit、push、创建 implement change。

## Decisions

### D1 — PostgreSQL 16 生产（ADR-003d）

Alembic 权威方言 PG 16；SQLite 开发/单测；CI 双轨；连接串环境变量；无真实密码入仓。

### D2 — party_risk_events 首版（ADR-003e）

当前 risk_status 在 parties；完整历史在不可变事件表；同事务 + audit_logs；权限 risk_read / risk_manage。

### D3 — 旧接口 v2.0.0 + NOT_READY（ADR-003f）

门禁全满足后独立 change 删除；否则即使到版本仍保留兼容层。

### D4 — 既有决策保留

manage_unscoped、party_role_id、无证件列、ACTIVE 部分唯一索引（PG 权威）等。

## Risks / Trade-offs

| 风险 | 缓解 |
| --- | --- |
| 仅 SQLite 绿 | 强制 PG 集成测门禁 |
| 风险原因过度暴露 | risk_read 与 read 分离 |
| 兼容层滞留 | v2.0.0 目标 + 可度量门禁 |

## Migration Plan

无运行时迁移。批准后 `implement-party-master`：PG 测试骨架 → Alembic → 领域/API → adapter。

## Open Questions

### 已决策

见领域设计 §2.1。

### 非阻塞实施参数

见领域设计 §2.2。

### 结构性 Open Questions

**无。**
