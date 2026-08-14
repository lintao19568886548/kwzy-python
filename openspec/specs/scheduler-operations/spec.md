# scheduler-operations Specification

## Purpose

Define allow-listed durable scheduling, concurrent claims, recovery and scoped operational observability.

## Requirements

### Requirement: Allow-listed scheduler definitions
The system SHALL persist schedules only for code-registered handlers with validated bounded parameters, cadence and concurrency policy, and SHALL reject command lines, module paths, SQL and URLs.

#### Scenario: Unknown handler
- **WHEN** an administrator creates a schedule with an unregistered handler key
- **THEN** the command fails without persisting the schedule

### Requirement: Concurrent safe claims and durable runs
The system SHALL claim due enabled schedules with database locking and SHALL record a durable run, claim token, attempt, heartbeat and terminal result.

#### Scenario: Two scheduler workers
- **WHEN** two workers poll the same due schedule concurrently on PostgreSQL
- **THEN** only one active run is created for the schedule and fire time

### Requirement: Failure recovery and retry
The system SHALL detect stale runs, preserve failure evidence, calculate the next fire time and allow an authorized idempotent manual retry.

#### Scenario: Worker stops after claim
- **WHEN** a RUNNING job stops heartbeating past its timeout
- **THEN** recovery marks it failed and makes the schedule eligible according to policy

#### Scenario: Repeated retry key
- **WHEN** the same manual retry idempotency key is submitted twice
- **THEN** the same run result is returned without executing the handler twice

### Requirement: Scheduler observability and scope
The system SHALL expose permission- and tenant-scoped definitions, due state, run history, duration, attempts and sanitized errors without exposing secrets.

#### Scenario: Parameter contains secret key
- **WHEN** a schedule parameter or error includes a registered secret field
- **THEN** APIs and audit details return a redacted representation
