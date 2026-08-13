# unit-opportunity-locking Specification

## Purpose
定义授权园区内可解释房源匹配、排他限时锁房、到期释放，以及与线索转化和合同激活的一致性规则。该规格确保并发竞争只有一个获胜者，且失败回滚不会遗留主体、合同、锁或单元状态污染。

## Requirements

### Requirement: Explainable unit matching
系统 MUST 只从线索授权园区的 current、VACANT、无有效锁单元中匹配，并返回面积、用途、价格维度的分数和理由及稳定排序。

#### Scenario: Match vacant units
- **WHEN** 负责人查询有面积和预算意向的开放线索房源匹配
- **THEN** 返回同园区可用单元及可解释得分，不包含 RETIRED/OCCUPIED/其他园区单元

### Requirement: Exclusive expiring unit lock
具备 `lead:lock` 的负责人或管理员 MUST 能锁定匹配单元到受限过期时间；同一 current Unit 在任一时刻 MUST 至多存在一个 ACTIVE 锁。

#### Scenario: Concurrent lock race
- **WHEN** 两条线索并发锁定同一 VACANT current Unit
- **THEN** PostgreSQL 下只有一个 ACTIVE 锁和 RESERVED 投影，另一个返回 `UNIT_ALREADY_LOCKED` 409

#### Scenario: Expired lock releases inventory
- **WHEN** 有效锁超过 `expires_at` 且未被 Lease 激活消费
- **THEN** sweep 将锁标记 EXPIRED，并在无有效占用时把 Unit 恢复 VACANT

### Requirement: Lock-aware conversion and lease activation
Lead 转化 MUST 只能关联自身有效锁；创建 Lease DRAFT 后锁继续保留到期，Lease 激活 MUST 在同一 Unit 行锁内消费属于该合同的锁并投影 OCCUPIED。

#### Scenario: Foreign lock blocks activation
- **WHEN** Lease 尝试激活被其他线索有效锁定的 Unit
- **THEN** 激活失败且 Lease、锁和 Unit 状态全部不变

#### Scenario: Conversion rollback
- **WHEN** 带锁转化在 Party 或 Lease 创建后发生错误
- **THEN** 不产生 Party/Lease/锁关联残留，原锁与 Lead 保持可继续操作状态
