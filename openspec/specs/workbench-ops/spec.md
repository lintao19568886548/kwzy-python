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

### Requirement: Approval task work-item projection
The system SHALL create one idempotent `APPROVAL_TASK` work item per actionable approval task, assigned to the task candidate with matching park, priority, due time and approval deep link; the approval task SHALL remain the source of truth.

#### Scenario: Open step creates candidate work items
- **WHEN** a workflow step opens with two candidate tasks
- **THEN** two distinct OPEN work items are created using task ids as source ids

#### Scenario: Task terminal closes work item
- **WHEN** a task becomes approved, rejected, skipped or cancelled
- **THEN** its work item becomes done or cancelled in the same transaction

### Requirement: Approval overdue workbench consistency
An overdue approval sweep SHALL update the existing task work item to urgent without creating duplicates, and workbench summary counts SHALL reflect only still-actionable tasks visible to the current user.

#### Scenario: Repeated overdue sweep
- **WHEN** the overdue sweep runs twice for one pending task
- **THEN** the same work item remains OPEN and URGENT and no duplicate is created
