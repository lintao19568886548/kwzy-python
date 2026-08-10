# party-roles Specification

## Purpose
TBD - created by archiving change design-party-domain. Update Purpose after archive.
## Requirements
### Requirement: Business roles stored only on party_roles
Business role codes SHALL be stored only on party_roles (PROPERTY_OWNER, LESSEE, BROKER, SUPPLIER, PARTNER, CUSTOMER) and SHALL be the single source of truth for Party role codes.

#### Scenario: Assign lessee role
- **WHEN** LESSEE is added to a Party
- **THEN** a party_roles row exists without requiring a park relation

### Requirement: Roles independent of parks
Having a party_role SHALL NOT by itself create any park relation.

#### Scenario: Role without parks
- **WHEN** a Party has LESSEE role and zero park relations
- **THEN** the role remains valid and the Party is unscoped until a relation is created

### Requirement: CUSTOMER and LESSEE are distinct
CUSTOMER SHALL mean customer relationship and LESSEE SHALL mean actual lessee business role. A Party SHALL be allowed to hold both simultaneously. This stage SHALL NOT implement Lease behavior beyond defining the roles.

#### Scenario: Both customer and lessee
- **WHEN** CUSTOMER and LESSEE are active on one Party
- **THEN** both roles are stored

### Requirement: Deactivate role blocked by active park relations
Before deactivating a party_role, the system SHALL check for ACTIVE park relations referencing that party_role_id and SHALL reject deactivation with a business conflict if any exist.

#### Scenario: Role in use
- **WHEN** an ACTIVE park relation references the role
- **THEN** deactivate fails with PARTY_ROLE_IN_USE or equivalent

### Requirement: Party roles are not RBAC
Party business roles SHALL NOT grant Identity login permissions and SHALL NOT be mixed with system RBAC roles.

#### Scenario: Role assignment does not grant permissions
- **WHEN** a party_role is assigned
- **THEN** no Identity permission grant is created

