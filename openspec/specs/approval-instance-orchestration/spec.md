# approval-instance-orchestration Specification

## Purpose
TBD - created by archiving change complete-platform-approval-audit-center. Update Purpose after archive.
## Requirements
### Requirement: Version-bound approval submission
The system SHALL submit an approval against one active published definition version, persist a non-sensitive business snapshot, generate a tenant-unique request number, open the first step and atomically record submission events, tasks, work items and audit evidence.

#### Scenario: Submission is atomic
- **WHEN** task generation, work-item projection or audit recording fails
- **THEN** the approval request, events and all derived rows roll back together

#### Scenario: Duplicate business submission is idempotent
- **WHEN** the same tenant, business type, business id and idempotency key are submitted again
- **THEN** the existing approval is returned without duplicate tasks or events

### Requirement: Deterministic multi-step decisions
The system SHALL advance ordered steps according to `ANY` or `ALL` semantics, SHALL complete the instance only after every required step passes, and SHALL terminate actionable tasks on reject, return or withdraw.

#### Scenario: Any step advances on first approval
- **WHEN** one candidate approves a pending `ANY` step
- **THEN** sibling tasks close, the next step opens, and the instance remains pending unless it was the last step

#### Scenario: All step waits for threshold
- **WHEN** fewer than the required candidates approve an `ALL` step
- **THEN** the step and instance remain pending and the remaining candidate tasks stay actionable

#### Scenario: Reject closes the instance
- **WHEN** an authorized candidate rejects a pending task with a reason
- **THEN** the instance becomes rejected and all remaining open tasks/work items close atomically

### Requirement: Separation of duties and controlled return
The applicant MUST NOT decide their own task unless they hold the explicit override permission and provide a non-empty override reason; return SHALL require a reason and SHALL let only the applicant resubmit the same instance from the first step with a new round.

#### Scenario: Self approval denied
- **WHEN** an applicant attempts to approve without override permission
- **THEN** the system returns forbidden and leaves the instance, task, event and audit state unchanged

#### Scenario: Returned instance resubmitted
- **WHEN** the applicant resubmits a returned instance with the expected version
- **THEN** a new round of first-step tasks is generated without deleting the prior round history

### Requirement: Concurrent and idempotent commands
Decision, withdraw, return and resubmit commands SHALL use optimistic version checks and unique idempotency keys so concurrent or repeated submissions have one durable outcome and never double-advance a workflow.

#### Scenario: Concurrent decisions have one transition
- **WHEN** two approvers concurrently decide the same `ANY` step
- **THEN** exactly one step transition commits and the other response is the committed idempotent result or HTTP 409

#### Scenario: Repeated decision key is stable
- **WHEN** a client retries a completed decision with the same idempotency key and payload
- **THEN** the original result is returned without a second event, audit row or domain callback

### Requirement: Domain-owned business transitions
Bounded contexts SHALL invoke approval orchestration through commit-free ports and SHALL remain authoritative for business-state transitions; an approval status alone MUST NOT mutate an unrelated domain record.

#### Scenario: Lease approval commits with lease transition
- **WHEN** a Lease approval decision triggers a Lease state transition
- **THEN** approval tasks/events, Lease state, work items and audit evidence commit or roll back in one transaction
