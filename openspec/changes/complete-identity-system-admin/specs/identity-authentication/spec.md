## ADDED Requirements

### Requirement: Password login against tenant-scoped users
The system SHALL authenticate users by username and password against the application database for an active tenant. Login SHALL accept an optional `tenant_code`. When the same username exists in multiple active tenants and `tenant_code` is omitted, the system SHALL reject the request without issuing a token.

#### Scenario: Successful password login
- **WHEN** an active user submits valid credentials and a unique tenant resolution
- **THEN** the system returns an access token and user authorization summary without the password hash

#### Scenario: Ambiguous username
- **WHEN** the username exists in more than one active tenant and `tenant_code` is omitted
- **THEN** the system returns a tenant ambiguity error and does not issue a token

#### Scenario: Bad password
- **WHEN** credentials are invalid
- **THEN** the system returns an authentication failure without revealing whether the username exists beyond product-approved messaging

### Requirement: Login derives authorization from database relationships
The system SHALL derive action permissions and park scope from persisted user-role, role-permission, and park-scope relationships at login time. The system MUST NOT grant all-park access solely because authentication succeeded.

#### Scenario: Scoped user login claims
- **WHEN** a user has limited permissions and park scopes
- **THEN** the issued token claims contain those permissions and park scope mode LIST or NONE as configured

### Requirement: Optional SMS and page-access authentication remain gated
The system SHALL treat SMS login and page-access secondary verification as optional capabilities that MUST NOT be implemented until SMS provider, code storage, and rate-limit decisions are approved. Until then, related legacy endpoints remain documented as MISSING or HUMAN_DECISION_REQUIRED.

#### Scenario: SMS login blocked without decision
- **WHEN** SMS provider configuration is not approved
- **THEN** SMS login endpoints MUST NOT be advertised as production-ready COMPLETE
