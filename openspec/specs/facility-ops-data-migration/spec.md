# facility-ops-data-migration Specification

## Purpose
TBD - created by archiving change complete-facility-device-inspection-iot. Update Purpose after archive.
## Requirements
### Requirement: Legacy maintenance rows map through a versioned contract
Migration SHALL map authorized firefighting, transformer, elevator, hygiene and building-maintenance source rows into deterministic device identities, inspection occurrences and safe history using explicit park/unit/type/status/time mappings and stable source references.

#### Scenario: Repeated transformer inspection rows
- **WHEN** multiple valid legacy rows identify the same signed transformer identity
- **THEN** one device and ordered inspection occurrences are created without overwriting source evidence

### Requirement: Unsafe or ambiguous rows are quarantined
Missing tenant/park/device identity, impossible time ordering, unrecognized result/status, conflicting duplicate source keys, raw binary, unrestricted URLs and unmasked PII SHALL be quarantined with bounded reason and irreversible digest rather than guessed or silently dropped.

#### Scenario: Ambiguous firefighting name
- **WHEN** repeated names cannot be proven to identify one device
- **THEN** the rows are quarantined and no fabricated device merge occurs

### Requirement: Rehearsal is transactional idempotent and reconcilable
Dry-run, forced interruption, first apply, idempotent reapply, device/type/status/result/time/orphan/PII reconciliation and schema rollback SHALL execute on isolated PostgreSQL. A failure SHALL leave no partial target rows or authorization changes.

#### Scenario: Interrupted result migration
- **WHEN** migration fails after staging inspection results and is rerun
- **THEN** the first transaction leaves zero target rows and the rerun creates every valid source row once

### Requirement: Synthetic IoT evidence is not live migration
Synthetic alarm fixtures SHALL be marked non-production and SHALL NOT create provider delivery claims. Real migration/cutover SHALL require authorized schemas, desensitized samples, signed device/key maps, attachment inventory, vendor event dictionary, freeze point, reconciliation and production authorization.

#### Scenario: No authorized alarm export
- **WHEN** synthetic maintenance/alarm rehearsal passes without an authorized legacy/vendor export
- **THEN** status remains synthetic-ready and real cutover is BLOCKED
