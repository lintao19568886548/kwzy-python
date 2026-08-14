## ADDED Requirements

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
