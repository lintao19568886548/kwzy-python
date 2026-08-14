# workforce-employee-lifecycle Specification

## Purpose
TBD - created by archiving change complete-workforce-scheduling-attendance-performance. Update Purpose after archive.
## Requirements
### Requirement: Scoped workforce employee lifecycle
The system SHALL maintain tenant/park-scoped employees with unique workforce number, employment dates/status, optional identity link and immutable lifecycle history.

#### Scenario: Cross-park employee lookup
- **WHEN** a park-limited user requests an employee outside scope
- **THEN** the system returns 404 without disclosure

### Requirement: Employee PII is minimized
Raw mobile and government identity values SHALL become masked/fingerprint facts, be excluded from responses/logs, and never be stored in plaintext workforce columns.

#### Scenario: Employee creation response
- **WHEN** an authorized manager creates an employee with identity inputs
- **THEN** only masked facts and fingerprints are returned

### Requirement: Identity linkage is explicit and unique
An active identity user SHALL link to at most one active workforce employee per tenant, and binding SHALL require expected version and audit evidence.

#### Scenario: Duplicate active user binding
- **WHEN** the same user is linked to a second active employee
- **THEN** the command returns 409 and preserves the existing link
