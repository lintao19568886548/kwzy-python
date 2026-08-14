## ADDED Requirements

### Requirement: Synthetic migration covers legacy-shaped enterprise data
The migration rehearsal SHALL cover legacy rental-tenant/company profile fields, tags, company relationships, organization credential metadata and risk signals while keeping contract/rent facts out of Party and personal identifiers out of the target and evidence.

#### Scenario: Contract facts in source
- **WHEN** a legacy tenant row includes rent and contract dates
- **THEN** the Party migration maps only Party/profile facts and records contract fields as owned by the Lease migration rather than copying them to Party

### Requirement: Migration has dry-run and transactional apply
Dry-run SHALL validate and report planned create/update/link/quarantine counts without writes. Apply SHALL be transactional and SHALL roll back all target writes on an injected interruption.

#### Scenario: Interrupted apply
- **WHEN** the migration is interrupted after profile writes but before child completion
- **THEN** no partial profile, relationship, credential, tag or risk rows remain committed

### Requirement: Reapply is idempotent and reconciled
Migration source keys and fingerprints SHALL make reapply idempotent. Reconciliation SHALL compare per-object counts, orphan counts, duplicate active keys and deterministic checksums without raw PII.

#### Scenario: Second apply
- **WHEN** the same source fixture is applied twice
- **THEN** the second apply creates zero new business rows and reconciliation still passes

### Requirement: Unsafe legacy rows are quarantined
Rows with ambiguous Party matches, cross-tenant/unknown endpoints, missing attachments, unknown enums, invalid ownership, personal identity fields or unsupported provider claims SHALL be quarantined with source reference, issue code, field names and irreversible fingerprint only.

#### Scenario: Personal identity in source
- **WHEN** a legacy row contains a full personal identity number
- **THEN** it is not written to any target/evidence field and quarantine contains no reversible value

### Requirement: Rollback and real-data gates are explicit
The rehearsal SHALL prove data rollback and schema downgrade/upgrade. Overall real-data readiness SHALL remain blocked until an authorized legacy schema dump, desensitized sample and Party/park/user/attachment mappings are supplied and reconciled.

#### Scenario: Synthetic rehearsal succeeds
- **WHEN** every synthetic migration gate passes but no authorized legacy sample exists
- **THEN** the result is synthetic-ready-for-staging-data and not a real migration PASS
