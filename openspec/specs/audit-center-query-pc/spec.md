# audit-center-query-pc Specification

## Purpose
TBD - created by archiving change complete-platform-approval-audit-center. Update Purpose after archive.
## Requirements
### Requirement: Tenant and park scoped audit query
The system SHALL provide paginated audit search by actor, action, resource type/id, park, request id, integrity state and time range; every query SHALL enforce tenant isolation, explicit audit-read permission and park scope.

#### Scenario: Cross-tenant audit hidden
- **WHEN** a caller guesses an audit id from another tenant
- **THEN** detail returns a non-enumerating not-found response

#### Scenario: Park aggregate does not leak
- **WHEN** a LIST-scoped caller searches without a park filter
- **THEN** rows and totals include only tenant-wide events and accessible parks

### Requirement: Controlled detail and export
Audit detail SHALL return canonical redacted evidence and integrity fields; CSV export SHALL require a separate permission, reuse identical filters and scope, enforce a bounded row limit and record an audit event for the export without including exported row contents.

#### Scenario: Export permission denied
- **WHEN** an audit reader without `audit.export` requests export
- **THEN** the system returns forbidden and creates no file

#### Scenario: Export is itself audited
- **WHEN** an authorized export succeeds
- **THEN** a new audit event records filters, row count and request id but no exported business detail

### Requirement: Operable audit center PC
The PC system administration experience SHALL provide live audit search, filters, paginated results, integrity badges, a detail drawer and controlled export with loading, empty, read-only, permission, error/retry and responsive states.

#### Scenario: Verify from detail drawer
- **WHEN** an audit reader opens a new chained event
- **THEN** the drawer shows actor, action, target, time, request id, redacted detail and verified or failed integrity state

#### Scenario: Narrow viewport remains readable
- **WHEN** the audit center is used at tablet or mobile width
- **THEN** filters collapse, result rows remain readable and actions do not overlap or clip
