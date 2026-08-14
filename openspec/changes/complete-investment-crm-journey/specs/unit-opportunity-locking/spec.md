## MODIFIED Requirements

### Requirement: Exclusive expiring unit lock
具备 `lead:lock` 的负责人或管理员 MUST 只能凭同一 Lead 的未过期 APPROVED 意向版本锁定该版本覆盖的匹配单元到受限过期时间；续期 MUST 再次验证意向有效性。同一 current Unit 在任一时刻 MUST 至多存在一个 ACTIVE 锁，锁记录 MUST 保留授权意向及版本。

#### Scenario: Concurrent lock race
- **WHEN** 两条各自具有有效批准意向的线索并发锁定同一 VACANT current Unit
- **THEN** PostgreSQL 下只有一个 ACTIVE 锁和 RESERVED 投影，另一个返回 `UNIT_ALREADY_LOCKED` 409

#### Scenario: Expired lock releases inventory
- **WHEN** 有效锁超过 `expires_at` 且未被 Lease 激活消费
- **THEN** sweep 将锁标记 EXPIRED，并在无有效占用时把 Unit 恢复 VACANT

#### Scenario: Pending intent cannot lock
- **WHEN** a Lead owner attempts to lock a Unit using a pending, rejected, withdrawn, expired or foreign intent
- **THEN** the command fails without changing the Unit or creating a lock
