# asset-data-migration Specification

## Purpose
TBD - created by archiving change implement-asset-rent-control-v2. Update Purpose after archive.
## Requirements
### Requirement: Legacy asset disposition and mapping
The migration package SHALL disposition legacy park/factory/factory_floor/rental-manage endpoints and fields as mapped, transformed, approved-retire, approved-defer or blocked. It SHALL document hierarchy inference, unit code normalization, area/price precision, status mapping and unmappable rows.

#### Scenario: Mapping evidence is reviewed
- **WHEN** the asset migration documentation is inspected
- **THEN** every in-scope source group has a target or explicit disposition and no source field is silently discarded

### Requirement: Synthetic identity-safe migration drill
The repository SHALL provide a non-production synthetic drill covering dry-run validation, first PostgreSQL apply, idempotent re-apply, hierarchy/unit/lineage reconciliation and rollback in an isolated schema.

#### Scenario: Idempotent asset replay
- **WHEN** the same valid synthetic asset fixture is applied twice
- **THEN** the second apply creates no duplicates and source/target node, unit, area and lineage totals still reconcile

### Requirement: Dirty asset rows are quarantined
Rows with orphan parents, cyclic hierarchy, duplicate normalized codes, invalid numeric precision or inconsistent areas SHALL fail or be quarantined with stable reason codes rather than entering operational tables.

#### Scenario: Orphan floor is rejected
- **WHEN** a floor references a missing factory/building
- **THEN** the dry-run identifies the row as an orphan and apply does not create it

### Requirement: Real-data readiness remains gated
Production or staging migration readiness MUST remain blocked until an authorized read-only source schema/data sample is fingerprinted, reconciled and approved. Synthetic evidence SHALL NOT be represented as real-data proof.

#### Scenario: No authorized legacy snapshot
- **WHEN** only repository fixtures are available
- **THEN** the status remains conditional synthetic readiness and no production connection or cutover occurs
