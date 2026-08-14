## ADDED Requirements

### Requirement: Legacy repair orders map through a versioned contract
Migration SHALL map legacy order number, source, tenant/park/factory, repair type, description, bounded images, status, priority, assignee, process evidence and accept/finish/confirm timestamps into explicit WorkOrder/timeline records with stable source identity.

#### Scenario: Legacy waiting acceptance
- **WHEN** a valid `待验收` row has finish evidence but no confirmation time
- **THEN** it becomes `WAITING_ACCEPTANCE` with preserved finish event and no fabricated acceptance

### Requirement: Ambiguous and unsafe data is quarantined
Missing Party/park mapping, impossible timestamp/state combinations, duplicate conflicting order numbers, raw binary payloads, unrestricted URLs and unmasked phone fields SHALL be quarantined with source ref, bounded reason and irreversible digest rather than copied or silently dropped.

#### Scenario: Tenant label cannot map to Party
- **WHEN** a legacy row has only an ambiguous tenant name
- **THEN** it is quarantined and no guessed Party relation is created

### Requirement: Rehearsal is transactional, repeat-safe and reconcilable
Dry-run, forced interruption, apply, idempotent reapply, count/status/timestamp/cost/orphan/PII reconciliation and schema rollback SHALL run on isolated PostgreSQL. A failed run SHALL leave no partial target rows.

#### Scenario: Interrupted batch replay
- **WHEN** a migration fails after staging events and is rerun
- **THEN** the first transaction leaves zero target rows and the rerun creates each source order/event once

### Requirement: Synthetic readiness is not real cutover
The system SHALL require an authorized legacy schema dump, desensitized sample, Party/park/user mapping, attachment disposition, freeze point and signed reconciliation before real migration or cutover can pass.

#### Scenario: No authorized snapshot
- **WHEN** synthetic rehearsal passes but no authorized legacy snapshot exists
- **THEN** status remains synthetic-ready and real migration is BLOCKED
