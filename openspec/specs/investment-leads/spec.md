# investment-leads Specification

## Purpose
定义租户、园区和负责人范围内受治理的线索生命周期、阶段兼容、乐观并发与原子转化规则。该规格确保线索、主体、合同、锁房、待办和审计在成功或失败路径上保持一致且不泄露跨范围数据。

## Requirements

### Requirement: Lead lifecycle

系统 MUST 支持租户/园区/负责人范围内的线索创建、查询、阶段推进、输单、合并与原子转化；标准阶段 MUST 为 `NEW/CONTACTING/VISITING/QUOTING/NEGOTIATING/WON/LOST/CANCELLED/MERGED`，非法转换和过期版本 MUST 被拒绝。

#### Scenario: Create governed lead
- **WHEN** 具备 `lead:write` 的用户在授权园区提交合法且通过重复门禁的线索
- **THEN** 系统返回 `status=NEW`、私有负责人、`lock_version=1` 并创建首跟进待办

#### Scenario: Legacy following compatibility
- **WHEN** 兼容期客户端提交 `FOLLOWING`
- **THEN** 系统按 `CONTACTING` 持久化和响应，并不得继续产生新的 `FOLLOWING` 数据

#### Scenario: Atomic conversion
- **WHEN** 可转化线索创建 Party 和可选 Lease DRAFT 的任一步失败
- **THEN** Lead、Party、Lease、锁房关联、待办与审计 MUST 整体回滚

#### Scenario: Scoped permission denial
- **WHEN** 用户读取非本人且非公海的线索，或目标园区不在授权范围
- **THEN** 系统拒绝请求且不泄露外部租户/园区/负责人数据

#### Scenario: Stale update loses
- **WHEN** 两个请求用同一 `expected_version` 修改同一 Lead
- **THEN** 只有一个提交，另一个返回稳定的 409 版本冲突
