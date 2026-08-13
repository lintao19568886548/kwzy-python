# lead-assignment-pool Specification

## Purpose
定义线索负责人和公海的可见性、分配改派、领取释放与确定性超时回收规则。该规格确保每次所有权变化具有不可覆盖的事件证据，并在并发领取和幂等回收时维持单一正确负责人。

## Requirements

### Requirement: Owner and public pool visibility
系统 MUST 将 Lead 明确投影为私有或公海；普通 `lead:read` 用户只能读取本人私有明细和授权园区公海摘要，`lead:manage` 才能读取园区内全量。

#### Scenario: Owner-scoped list
- **WHEN** 普通销售请求线索列表
- **THEN** 列表只包含本人私有线索和脱敏公海摘要，不包含其他销售私有线索

### Requirement: Assignment lifecycle
系统 MUST 支持管理员分配/改派/释放/回收和销售领取，并为每次所有权变化追加不可覆盖的事件、操作者、原因和时间。

#### Scenario: Claim public lead
- **WHEN** 具备 `lead:claim` 的用户领取授权园区内仍在公海的线索
- **THEN** Lead 变为该用户私有、版本递增、打开跟进待办并追加 CLAIM 事件

#### Scenario: Concurrent claim
- **WHEN** 两个用户并发领取同一公海线索
- **THEN** PostgreSQL 下只有一个成为负责人，另一个返回 `LEAD_ALREADY_CLAIMED` 409

### Requirement: Deterministic recycle
系统 MUST 根据 `recycle_due_at` 和最后活动时间识别应回收线索，并允许 `lead:manage` 以幂等命令回收到公海。

#### Scenario: Recycle overdue lead
- **WHEN** 私有开放线索超过回收期限且没有更新活动
- **THEN** 回收清空负责人、取消旧负责人待办、追加 RECYCLE 事件并只执行一次
