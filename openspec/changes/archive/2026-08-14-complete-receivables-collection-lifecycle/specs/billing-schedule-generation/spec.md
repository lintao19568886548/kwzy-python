## ADDED Requirements

### Requirement: Current approved Lease schedules generate receivable Bills
The system SHALL select only current-version schedule rows for tenant/park-visible contracts in `ACTIVE`, `EXPIRING` or `EXIT_PENDING`, and SHALL group compatible rows into an issued Bill with one lineage-bound BillLine per schedule row.

#### Scenario: Monthly multi-fee schedule
- **WHEN** an active contract has rent and management schedule rows for the same period, due date and currency
- **THEN** one issued Bill is created with two lines whose total equals the schedule gross amounts

### Requirement: Billing runs support preview and apply
Preview SHALL return eligible groups, totals and conflicts without writes. Apply SHALL require `bill:generate`, an Idempotency-Key and an as-of date, and SHALL commit Bills, lines, schedule state, audit, work item and event atomically.

#### Scenario: Preview has no side effect
- **WHEN** a caller previews an eligible period
- **THEN** no Bill or schedule mutation is committed

### Requirement: Schedule lineage is repeat and concurrency safe
Each schedule row SHALL be billed at most once. Repeated or concurrent apply for the same rows SHALL return the same completed outcome or an explicit conflict, never duplicate receivables.

#### Scenario: Concurrent generation
- **WHEN** two PostgreSQL transactions apply the same eligible schedules
- **THEN** each schedule has exactly one BillLine and no duplicate Bill is committed

### Requirement: Issued history is not silently rewritten
If a contract version changes after a schedule was billed, the system SHALL retain the original Bill and report overlapping changed intent for governed adjustment rather than update or delete financial history.

#### Scenario: Changed billed period
- **WHEN** a new contract version changes an already billed period
- **THEN** the generation preview reports a conflict and the issued Bill remains unchanged
