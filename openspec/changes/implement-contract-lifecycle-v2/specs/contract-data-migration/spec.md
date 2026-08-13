## ADDED Requirements

### Requirement: Legacy contract disposition and mapping
The project MUST publish endpoint and field-level disposition for legacy `rental_tenant`, tenant images, contract reminders and related mixed customer/contract fields, including target Party/Lease/version/unit/charge/document/exit mappings, enum transforms, source keys, PII classification and unresolved fields.

#### Scenario: Mixed Party and contract row
- **WHEN** a legacy row contains company/contact fields together with contract dates and increase data
- **THEN** mapping separates Party identity from Lease facts, records stable source lineage and does not duplicate a Party solely because it has multiple contracts

#### Scenario: Unknown status or amount semantics
- **WHEN** repository evidence cannot prove an enum, unit, tax, deposit or balance meaning
- **THEN** the field is marked `BLOCKED_PENDING_SCHEMA_OR_SAMPLE` or quarantined and is never guessed into an active contract or financial clearance

### Requirement: Existing V1 contract backfill
Alembic/application migration MUST add new schema with a unique head, backfill lock/version/source projections deterministically and create immutable version 1 for existing ACTIVE, EXPIRING and terminal contracts from sorted current units and trusted terms. DRAFT/PENDING_ACTIVE contracts MUST remain pre-version and enter the new approval flow before activation.

#### Scenario: Backfill active contract
- **WHEN** migration upgrades a V1 ACTIVE contract with current unit and trusted term rows
- **THEN** it creates exactly one checksum-stable version 1, current charge/schedule projections as far as semantics are proven, and leaves Unit used_area reconciled

#### Scenario: Legacy renewed row
- **WHEN** V1 contains a RENEWED contract
- **THEN** migration preserves terminal history and source/successor evidence without creating a new RENEWED command path

#### Scenario: Migration down and up
- **WHEN** the CRM head upgrades to contract V2, downgrades one step and upgrades again on fresh PostgreSQL 16
- **THEN** Alembic always has one head and V2 tables/columns are created, removed and recreated without changing earlier migration files

### Requirement: Isolated idempotent contract drill
The contract ETL drill MUST accept only loopback non-production PostgreSQL and operate in isolated schema `etl_contract_lifecycle_fixture`. It MUST run dry-run, first apply, identical re-apply, reconciliation and schema-drop rollback over synthetic traditional-contract, attachment and reminder-like fixtures.

#### Scenario: Reapply fixtures
- **WHEN** the identical synthetic source set is applied twice
- **THEN** the second apply inserts zero Parties, contracts, versions, units, charges, schedules, documents and quarantines, with source references and checksums unchanged

#### Scenario: Unsafe database target
- **WHEN** the connection host is non-loopback or database identity appears production-like
- **THEN** the drill refuses before creating a schema or reading fixture PII

### Requirement: Contract reconciliation
The drill MUST reconcile source/target Party and contract counts, status/type/park distributions, version/unit/charge/schedule/document/reminder counts, occupied area, deposit/charge totals, duplicate source refs, orphans, checksum stability and PII quarantine, and output machine-readable JSON.

#### Scenario: Clean synthetic reconciliation
- **WHEN** all valid fixtures complete first apply
- **THEN** expected counts/distributions/totals match, duplicates/orphans are zero and raw quarantined PII is not persisted

#### Scenario: Rollback
- **WHEN** the drill completes or fails after schema creation
- **THEN** rollback removes only `etl_contract_lifecycle_fixture`, confirms absence and leaves public/application schemas untouched

### Requirement: Real data and cutover remain gated
Synthetic PASS MUST report only `CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA`. Reading a real schema/sample, resolving PII, incremental synchronization, stop-write, production migration, signing or financial cutover MUST require explicit human authorization and separate evidence.

#### Scenario: No authorized legacy snapshot
- **WHEN** only repository documents and synthetic fixtures are available
- **THEN** real legacy readiness remains `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE` and no production connection or deployment command is executed
