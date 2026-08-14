# inspection-execution-exception Specification

## Purpose
TBD - created by archiving change complete-facility-device-inspection-iot. Update Purpose after archive.
## Requirements
### Requirement: Inspection execution is assigned and versioned
Only the current assignee or an authorized manager SHALL start or submit an inspection task. PENDING to IN_PROGRESS to submitted terminal transitions SHALL require the expected aggregate version and retain assignment history.

#### Scenario: Former assignee submits after reassignment
- **WHEN** a former assignee submits results after the task was reassigned
- **THEN** the request is denied and task/results remain unchanged

### Requirement: Results match the snapshotted checklist
Submission SHALL provide exactly one bounded typed result for every required snapshotted item, safe evidence references and an optional bounded remark. Unknown, duplicate, missing or type-invalid item results SHALL fail atomically.

#### Scenario: Missing critical result
- **WHEN** a submission omits a required critical item
- **THEN** no result or task state change is persisted

### Requirement: Failed checks create governed exceptions and remediation
A failed result SHALL append an InspectionException. A failed critical result SHALL atomically create or reuse one linked WorkOrder using a stable source id, while non-critical failures SHALL require authorized promotion before WorkOrder creation.

#### Scenario: Critical fire item fails twice on retry
- **WHEN** the same inspection submission is retried with the same idempotency key
- **THEN** one exception and one linked WorkOrder exist without duplicate WorkItems or outbox events

### Requirement: Missed inspection escalation is truthful and repeat-safe
An overdue PENDING or IN_PROGRESS task SHALL become MISSED through a sweep that appends at most one missed event, closes or escalates the field WorkItem and creates an exception according to schedule policy. Completed/cancelled tasks SHALL never be marked missed.

#### Scenario: Repeated missed sweep
- **WHEN** the overdue sweep runs twice for the same task
- **THEN** one MISSED transition and one configured escalation exist
