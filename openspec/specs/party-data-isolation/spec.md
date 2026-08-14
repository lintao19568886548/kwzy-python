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

### Requirement: Enterprise profile graph is tenant isolated
All profile, relationship, credential, tag, risk and resolution queries/writes SHALL derive tenant id from authenticated context and enforce tenant-scoped parent/child foreign keys. Client tenant ids SHALL be forbidden.

#### Scenario: Fabricated tenant id
- **WHEN** a request includes another tenant id in any body or query field
- **THEN** strict validation rejects it and no cross-tenant data is accessed

### Requirement: Relationship visibility requires both endpoints
A related-company edge SHALL be returned or mutated only when both endpoint Parties are visible under the caller's Party park scope, except an authorized `party:manage_unscoped` caller may manage an edge whose endpoints are both unscoped.

#### Scenario: One endpoint outside park scope
- **WHEN** the source Party is visible but the target Party has active relations only outside the caller's park scope
- **THEN** the relationship is hidden and identifier access returns not found

### Requirement: Enterprise child writes follow Party write visibility
Profile, relationship and tag writes SHALL require `party:write` plus existing Party visibility, or `party:manage_unscoped` for an unscoped Party. Credential and risk actions SHALL additionally require their dedicated permissions and SHALL not be granted by park scope alone.

#### Scenario: All parks without credential permission
- **WHEN** a caller has all-parks scope and party:write but lacks party:credential_manage
- **THEN** credential creation is denied

### Requirement: Field-level details are permission filtered
Enterprise directory/detail serializers SHALL omit credential detail without `party:credential_read` and omit local risk summary/history without `party:risk_read`. Query filters on hidden fields SHALL also require the matching read permission.

#### Scenario: Hidden risk filter
- **WHEN** a party:read-only caller supplies a local risk severity filter
- **THEN** the API denies the filter rather than revealing matching counts

### Requirement: Enterprise writes audit without sensitive payloads
Successful profile, relationship, credential, tag and risk-resolution writes SHALL commit audit records in the same transaction. Audit detail SHALL use ids, state transitions, masked suffixes and safe codes only, excluding raw identifiers, full contact/address values and risk evidence content.

#### Scenario: Credential audit
- **WHEN** a credential is created with an identifier and attachment
- **THEN** audit includes credential/Party/attachment ids and type but not the raw identifier or attachment content

