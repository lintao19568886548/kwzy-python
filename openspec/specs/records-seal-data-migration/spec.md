# records-seal-data-migration Specification

## Purpose
TBD - created by archiving change complete-records-signature-seal-governance. Update Purpose after archive.
## Requirements
### Requirement: Legacy evidence and mappings are versioned
The repository SHALL document legacy archive/signature/seal presence or absence, source field mappings, category/owner/park keys, file checksums, unsupported states and quarantine codes without inventing unavailable records.

#### Scenario: No legacy seal table
- **WHEN** static evidence finds no legacy seal aggregate
- **THEN** migration maps zero seals and does not fabricate registry or custody rows

### Requirement: Rehearsal is repeatable and recoverable
Synthetic migration SHALL support dry-run, transactional apply, injected interruption, reapply, reconciliation and rollback. Reapply SHALL create no duplicate record number, revision, checksum or provider event.

#### Scenario: Interrupted checkpoint
- **WHEN** failure is injected after mapping but before commit
- **THEN** no partial target rows remain and a subsequent apply succeeds

### Requirement: Unsafe or ambiguous rows are quarantined
Rows with unknown owner/park/category, missing binary/checksum, unrestricted URL, raw identity material, inconsistent signature claims or ambiguous duplicates SHALL be quarantined with source reference, issue code and irreversible fingerprint.

#### Scenario: Legacy signed flag without provider evidence
- **WHEN** a source row says signed but has no certificate/provider event
- **THEN** it is not imported as live signed and is quarantined or marked unverified

### Requirement: Real migration remains blocked without authorized inputs
Overall real-data readiness SHALL remain blocked until authorized schema/dictionaries, desensitized metadata and binaries, checksum inventory, key maps, category/retention decisions, provider evidence and signed reconciliation are supplied. Production deletion/cutover SHALL require separate authorization.

#### Scenario: Synthetic rehearsal passes alone
- **WHEN** all synthetic stages pass but authorized legacy inputs are absent
- **THEN** readiness is conditional synthetic-ready and real migration remains BLOCKED
