## ADDED Requirements

### Requirement: Explicit legacy disposition
The migration package SHALL map or explicitly block legacy workspace logs, outbox, consumer logs, in-app notifications and job definitions without inferring business ownership or successful delivery.

#### Scenario: Recipient mapping missing
- **WHEN** a legacy notification recipient cannot be mapped to an authorized V2 user
- **THEN** the row is blocked with a reason and no fabricated recipient is created

### Requirement: Reversible schema-versioned rehearsal
The migration tool SHALL support dry-run, apply, interruption rollback, idempotent repeat, reconciliation and fixture rollback on an isolated test database.

#### Scenario: Apply repeats
- **WHEN** the same approved synthetic package is applied twice
- **THEN** counts, identities and checksums remain stable with no duplicate active records

#### Scenario: Injected interruption
- **WHEN** the rehearsal fails during apply
- **THEN** all rows in that transaction roll back and a later retry succeeds

### Requirement: No secret or production access
The rehearsal SHALL contain no raw credentials/PII, SHALL reject non-test database targets and SHALL not contact production or external delivery providers.

#### Scenario: Non-test target
- **WHEN** the tool is pointed at a database not explicitly marked for migration testing
- **THEN** it fails closed before modifying data
