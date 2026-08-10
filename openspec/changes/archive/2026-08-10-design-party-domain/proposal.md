## Why

Party 设计经多轮评审后三项终局决策已定：生产方言 PostgreSQL 16、首版风险事件表、旧接口目标 v2.0.0 与门禁。须冻结设计包供最终人工批准，再允许独立 implement change。

## What Changes

**仅设计修订**；不 apply、不编码、不迁移、不提交推送、不创建 implement change。

- 生产 **PostgreSQL 16**；SQLite 仅开发/单测；Alembic 以 PG 为权威（ADR-003d）  
- 首版 **`party_risk_events`**；权限 **`party:risk_read` / `party:risk_manage`**（ADR-003e）  
- 风险动作专用 API；禁止 PATCH risk_status  
- 旧接口 **`removal_target_version: v2.0.0`**，**`removal_gate_status: NOT_READY`**（ADR-003f）  
- 清除结构性 Open Questions；保留非阻塞实施参数  

## Capabilities

### New Capabilities

- `party-domain`  
- `party-park-relations`  
- `party-roles`  
- `party-risk-status`  
- `party-contacts`  
- `party-api`  
- `party-data-isolation`  
- `party-compatibility`  
- `party-persistence-dialect`（生产 PG 与测试分工）  

### Modified Capabilities

- （无修改已归档 Step1 正式 spec 行为）

## Impact

| 面 | 说明 |
| --- | --- |
| 文档/ADR/OpenSpec | 本修订 |
| 实现 | 批准后建议 change：`implement-party-master` |
| 代码/库 | 本阶段无 |
