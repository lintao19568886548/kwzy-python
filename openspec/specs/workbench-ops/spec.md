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

### Requirement: Source-owned work item transitions
The system SHALL prevent ordinary manual commands from closing or reopening event/source-owned work items; only the owning projection or an explicit override permission with reason may do so.

#### Scenario: User completes approval task projection
- **WHEN** a normal user calls work-item complete for an open APPROVAL_TASK projection
- **THEN** the command is rejected and the approval task remains the source of truth

### Requirement: Optimistic work item update and deep link
The system SHALL expose safe registered deep links and lock versions, and SHALL require expected version for user-driven transitions or reassignment.

#### Scenario: Concurrent completion
- **WHEN** two commands transition the same manual work item using one expected version
- **THEN** one succeeds and one receives 409 without lost update

### Requirement: Idempotent escalation and reassignment
The system SHALL raise escalation level and optionally reassign an open work item once per event/rule action while retaining the prior assignee and audit history.

#### Scenario: Repeated escalation event
- **WHEN** the same escalation action is delivered twice
- **THEN** escalation level, assignee and notification change at most once

### Requirement: Event source coverage
Registered Lease, Billing, Approval, Investment and Facility lifecycle events SHALL be capable of creating or closing work-item projections through the same idempotent rule/event path.

#### Scenario: Registered bill event
- **WHEN** a BILL_ISSUED event matches a published collection rule
- **THEN** one scoped source-owned work item is available in the recipient workbench
