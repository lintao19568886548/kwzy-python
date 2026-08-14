## ADDED Requirements

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
