## ADDED Requirements

### Requirement: Database-derived organization governance permissions
The system SHALL authorize organization hierarchy, position assignment, and field policy operations using current-tenant database role permissions and MUST ignore client-declared role, permission, or field access claims.

#### Scenario: Fabricated permission rejected
- **WHEN** a client without `identity.org_governance.write` submits a write request and declares that permission in the request body or header
- **THEN** the system returns forbidden and persists no business or success audit row

#### Scenario: Revoked permission takes effect through session controls
- **WHEN** an administrator removes an organization governance permission from a role
- **THEN** affected sessions are invalidated under the existing token-version policy and subsequent writes are denied
