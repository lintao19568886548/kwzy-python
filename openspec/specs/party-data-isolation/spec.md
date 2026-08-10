# party-data-isolation Specification

## Purpose
TBD - created by archiving change design-party-domain. Update Purpose after archive.
## Requirements
### Requirement: Tenant isolation on Party graph
All Party, party_roles, party_park_relations, party_contacts, and party_risk_events operations SHALL filter by authenticated tenant_id.

#### Scenario: Cross-tenant hidden
- **WHEN** tenant A requests tenant B party id
- **THEN** not found without leakage

### Requirement: Unscoped manage permission
The permission code party:manage_unscoped SHALL authorize management of Parties with no ACTIVE park relations. all_parks, party:read, and party:write SHALL NOT automatically grant it. Action super-permission star MAY include the action but SHALL NOT bypass park data scope for scoped resources. Creates, updates, and first park assignments for unscoped parties SHALL be audited.

#### Scenario: Read without unscoped cannot list zero-relation parties
- **WHEN** a user has party:read but not manage_unscoped and a Party has no park relations
- **THEN** that Party is not listed

### Requirement: Scoped access after first relation
After a Party has ACTIVE park relations, access SHALL use park scope intersection with those parks or all-parks, plus party:read or party:write as applicable.

#### Scenario: First park assignment
- **WHEN** manage_unscoped user assigns first park relation
- **THEN** subsequent visibility follows park scope for other users

### Requirement: Action permission independent of park scope
party:write SHALL NOT grant all parks. all_parks SHALL NOT grant party:write without the permission or star.

#### Scenario: All parks without write
- **WHEN** user has all parks but not party:write and not star
- **THEN** create fails with PERMISSION_DENIED

### Requirement: Successful writes audited
Successful writes for Party master, roles, relations, contacts, archive, restore, and risk actions SHALL audit in the same transaction with non-sensitive detail. Risk actions SHALL also append party_risk_events as specified.

#### Scenario: Create audited
- **WHEN** party create commits
- **THEN** audit_logs contains PARTY create

### Requirement: New system database only
Party design and implementation SHALL use only the new-system database configuration and MUST NOT connect to legacy Java databases. Production dialect requirements are defined by party-persistence-dialect.

#### Scenario: No legacy datasource
- **WHEN** Party is implemented
- **THEN** repositories use the application new-system session only

