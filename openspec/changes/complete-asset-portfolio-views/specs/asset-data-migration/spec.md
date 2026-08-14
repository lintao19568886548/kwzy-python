## ADDED Requirements

### Requirement: Template and geometry legacy disposition
The migration package SHALL map known legacy asset types and bounded facility fields to exact V2 template versions, map coordinates only when their reference is known, and quarantine unknown types, invalid attributes or ambiguous coordinates without guessing.

#### Scenario: Unknown coordinate reference
- **WHEN** a legacy factory contains coordinates with no documented CRS
- **THEN** the geometry is quarantined with a reason while non-geometric asset facts may continue through reconciliation

### Requirement: Portfolio reconciliation
The rehearsal SHALL reconcile template/version counts, unit bindings, geometry counts, current/historical area, status and effective lease relationships after dry-run, apply, interruption recovery, idempotent repeat and rollback.

#### Scenario: Repeated asset portfolio apply
- **WHEN** the same approved synthetic package is applied twice
- **THEN** checksums and reconciled counts remain stable with no duplicate templates, versions, units or geometries
