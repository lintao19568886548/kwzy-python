## ADDED Requirements

### Requirement: Dispatch rules are versioned and deterministic
Assignment rules SHALL be drafted, published as immutable versions and retired explicitly. Matching SHALL order by tenant, park specificity, category, priority, configured order and stable id; the applied rule version SHALL be snapshotted on the WorkOrder.

#### Scenario: Two matching rules
- **WHEN** a park-specific rule and tenant-wide fallback both match a request
- **THEN** the park-specific published rule wins deterministically and its version is recorded

### Requirement: Unmatched work is visible, not silently assigned
If no published rule matches, the WorkOrder SHALL remain `SUBMITTED` and create an unassigned triage WorkItem. The system SHALL NOT report dispatch success.

#### Scenario: No configured electrician
- **WHEN** an electrical request has no matching active rule
- **THEN** it remains unassigned with a triage task and truthful dispatch status

### Requirement: Manual reassignment is governed
Dispatch/reassignment SHALL require permission, expected aggregate version, same-tenant assignee, park eligibility and a bounded reason. Prior assignment evidence SHALL remain append-only.

#### Scenario: Stale reassignment
- **WHEN** two managers reassign the same version concurrently
- **THEN** exactly one succeeds and the stale request receives 409 without a second active task owner

### Requirement: SLA state is derived and escalation is repeat-safe
Response and resolution deadlines SHALL be snapshotted from the applied rule. First response SHALL be set once. A sweep SHALL append at most one event per SLA boundary and project a truthful on-track/breached/completed state.

#### Scenario: Repeated breach sweep
- **WHEN** the SLA sweep runs twice after the response deadline
- **THEN** one response-breach event and one escalation projection exist
