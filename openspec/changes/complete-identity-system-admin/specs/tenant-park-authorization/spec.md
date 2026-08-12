## ADDED Requirements

### Requirement: Tenant isolation on identity administration
The system SHALL scope all user, role, permission-binding, and park-scope administration reads and writes to the authenticated tenant_id. Cross-tenant identifiers MUST NOT be readable or writable.

#### Scenario: Cross-tenant user id access
- **WHEN** an admin supplies a user id belonging to another tenant
- **THEN** the system returns not-found or forbidden without leaking existence details beyond envelope policy

### Requirement: Manage park scopes for users and roles
The system SHALL provide APIs to grant and revoke park data scopes for users and/or roles, including explicit all-parks grants. Park scope mode SHALL be one of ALL, LIST, or NONE.

#### Scenario: Grant listed parks
- **WHEN** an admin assigns park ids 10 and 20 to a user or role
- **THEN** subsequent authorization resolution yields LIST with those park ids (union rules as designed)

#### Scenario: Explicit all-parks grant
- **WHEN** an admin sets all-parks for a principal
- **THEN** park_scope_mode becomes ALL independent of action permission codes

### Requirement: Empty park scope denies park-scoped data
The system SHALL treat empty park scope without ALL as NONE. Park-scoped business APIs MUST NOT treat empty lists as unrestricted.

#### Scenario: Empty scope list is not all access
- **WHEN** park_scope_mode is NONE or LIST with empty ids
- **THEN** park-scoped list endpoints return empty data or 403 per existing park-scope rules
