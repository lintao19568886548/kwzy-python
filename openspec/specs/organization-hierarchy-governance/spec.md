# organization-hierarchy-governance Specification

## Purpose
Define tenant-scoped group and region masters with effective-dated, auditable park assignment history.

## Requirements

### Requirement: Tenant-scoped group and region hierarchy
The system SHALL maintain groups and regions as tenant-scoped masters, SHALL require a region to reference a group from the same tenant, and SHALL enforce tenant-local unique codes.

#### Scenario: Create hierarchy in current tenant
- **WHEN** an authorized administrator creates a group and then a region in that group
- **THEN** the system persists both under the request tenant and returns them in hierarchy order

#### Scenario: Cross-tenant parent rejected
- **WHEN** an administrator references a group belonging to another tenant
- **THEN** the system returns a non-enumerating not-found response and writes no region

### Requirement: Historical region-to-park governance
The system SHALL preserve effective-dated region-to-park assignment history and MUST allow at most one current region assignment for each tenant park.

#### Scenario: Reassign park preserves history
- **WHEN** an authorized administrator reassigns an accessible park from region A to region B
- **THEN** the system closes the region A assignment, creates a current region B assignment, and exposes both records in chronological history

#### Scenario: Concurrent current assignment has one winner
- **WHEN** two transactions concurrently assign different current regions to the same park
- **THEN** the database accepts at most one current assignment and the losing API returns a conflict

### Requirement: Dependency-safe lifecycle and audit
The system SHALL reject disabling a group with active regions and disabling a region with a current park assignment, and every successful hierarchy write SHALL record a redacted audit entry in the same transaction.

#### Scenario: Disable region with park rejected
- **WHEN** an administrator disables a region that still owns a current park assignment
- **THEN** the system returns a conflict and neither the resource nor audit trail claims success

#### Scenario: Successful reassignment audited atomically
- **WHEN** park reassignment commits
- **THEN** the old and new assignment state and a non-sensitive audit record commit together
