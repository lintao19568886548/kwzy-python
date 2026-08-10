# party-park-relations Specification

## Purpose
TBD - created by archiving change design-party-domain. Update Purpose after archive.
## Requirements
### Requirement: Relations reference party_role_id only
party_park_relations SHALL store party_role_id referencing party_roles and SHALL NOT store a separate relation_role string code.

#### Scenario: Create relation uses party_role_id
- **WHEN** a park relation is created
- **THEN** it references an existing party_role_id for the same tenant and party

### Requirement: party_role_id must match party and tenant
The system SHALL reject party_role_id values that belong to another party or tenant.

#### Scenario: Cross-party role rejected
- **WHEN** party_role_id belongs to a different party
- **THEN** creation fails with PARTY_ROLE_MISMATCH or equivalent

### Requirement: Active relation uniqueness business key
Within a tenant, only one ACTIVE non-soft-deleted relation SHALL exist for the same party_id, park_id, and party_role_id.

#### Scenario: Duplicate active relation rejected by application
- **WHEN** an ACTIVE relation already exists for the tuple
- **THEN** create fails with PARTY_PARK_RELATION_DUPLICATE before relying solely on races

### Requirement: Database enforces active uniqueness
The database SHALL enforce active relation uniqueness as the final guarantee. For SQLite and PostgreSQL the design SHALL use a partial unique index on (tenant_id, party_id, park_id, party_role_id) WHERE status is ACTIVE and deleted_at is NULL. For MySQL the design SHALL use an equivalent approach such as a nullable active_guard generated column included in a unique key. Implementation MUST NOT rely on application checks alone.

#### Scenario: Concurrent create one fails at database
- **WHEN** two concurrent creates race for the same active tuple
- **THEN** at most one commits and the other becomes a mapped business conflict without leaking SQL

### Requirement: Ended relations allow a new active relation
After an ACTIVE relation is ended, a new ACTIVE relation for the same tuple SHALL be allowed. Multiple historical non-ACTIVE relations MAY coexist. Historical relations SHALL NOT be physically deleted by default.

#### Scenario: Re-link after end
- **WHEN** prior relation is ENDED and a new ACTIVE relation is created for the same tuple
- **THEN** creation succeeds

### Requirement: Visibility uses relations and park scope
Visibility for parties with relations SHALL use intersection of user park scope and ACTIVE related parks, or all-parks scope within the tenant.

#### Scenario: Scoped user does not see unrelated park party
- **WHEN** user LIST scope is park A and party relates only to park B
- **THEN** the party is not visible

### Requirement: Multi-park without duplicate masters
The system SHALL associate one Party master to multiple parks via relations and SHALL NOT create duplicate masters for multi-park coverage.

#### Scenario: Second park adds relation
- **WHEN** the same Party needs another park under a role
- **THEN** a new relation row is added rather than a new Party master

