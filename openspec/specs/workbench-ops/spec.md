# workbench-ops Specification

## Purpose

Define the operational workbench contract for lifecycle-derived work items and tenant-scoped summary metrics.

## Requirements

### Requirement: Contract expiring work item

系统 MUST 在合同激活时幂等创建 `source_type=LEASE`、`item_type=CONTRACT_EXPIRING` 待办；终止或违约 MUST 取消该待办。

#### Scenario: Activate opens todo

- **WHEN** 用户激活合同
- **THEN** 存在一条 OPEN 待办且 source_id 等于合同 id

#### Scenario: Terminate cancels todo

- **WHEN** 用户终止合同
- **THEN** 对应待办状态为 CANCELLED

### Requirement: Workbench summary

系统 MUST 提供 `GET /workbench/summary`，返回 open/overdue/due_soon 待办计数、未结账单数、即将到期合同数及最近待办列表。

#### Scenario: Summary requires read permission

- **WHEN** 调用方无 `work_item:read`
- **THEN** 返回 403 PERMISSION_DENIED
