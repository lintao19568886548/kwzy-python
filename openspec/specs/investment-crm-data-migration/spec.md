# investment-crm-data-migration Specification

## Purpose
定义传统招商、CRM 与 radar-like 旧数据的处置、字段映射、隐私隔离和迁移演练规则。该规格确保合成数据验证与真实数据授权、预发切换及生产操作之间保持清晰且可审计的安全边界。

## Requirements

### Requirement: Legacy dual-track disposition and mapping
系统 MUST 发布传统 `investment`、CRM lead 表族和 radar external lead 的保留/合并/延后处置，以及 Lead、活动、分配、来源和匹配字段级转换、枚举、PII 与无法映射清单。

#### Scenario: Unverified legacy field
- **WHEN** 仓库证据无法确定旧字段含义或合法枚举
- **THEN** 映射标记 `BLOCKED_PENDING_SCHEMA_OR_SAMPLE`，不得猜测或连接生产库验证

### Requirement: Idempotent isolated CRM drill
迁移工具 MUST 只允许 loopback 非生产 PostgreSQL，在独立 schema 中支持 dry-run、首次 apply、幂等 re-apply、对账和删除该 schema 的回滚。

#### Scenario: Reapply same fixtures
- **WHEN** 相同传统/CRM/radar-like 合成 fixture 第二次导入
- **THEN** leads、activities、assignment events 和 merge links 新增数均为 0，来源外部键保持唯一

### Requirement: CRM reconciliation
演练 MUST 对账来源/目标线索数、阶段/公海/负责人分布、活动/分配/合并数、重复来源键、孤儿引用和 PII 拒绝/隔离数。

#### Scenario: Clean reconciliation
- **WHEN** 所有合法 fixture 完成导入
- **THEN** 各项计数相等、零孤儿/重复来源键，并输出机器可读 JSON 报告

### Requirement: Real data and cutover gate
真实 schema/数据读取、增量同步、停写、生产迁移和切换 MUST 保持人工授权门禁，合成 PASS 只能标记 `CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA`。

#### Scenario: No authorized legacy snapshot
- **WHEN** 只有仓库文档和合成 fixture
- **THEN** readiness 保持 conditional，工具不执行生产连接、真实 PII 导出或切换
