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

### Requirement: Authentication attempts are rate limited
The system SHALL rate-limit password and verification-code attempts using a shared store and stable account/IP digests. Responses MUST NOT reveal whether an account exists and logs MUST NOT contain submitted passwords or codes.

#### Scenario: Repeated bad password
- **WHEN** the configured account or client-IP threshold is exceeded within the window
- **THEN** the system returns 429 with a stable rate-limit error and does not evaluate more passwords until the retry window

### Requirement: SMS and page-access verification are provider neutral
The system SHALL support expiring, one-time verification codes and short-lived page-access proofs through a provider-neutral SMS port. Local/test MAY use a fake provider; staging/production SHALL fail closed when the selected real provider is not configured and MUST remain NOT_LIVE until real sandbox evidence exists.

#### Scenario: Verification code is consumed
- **WHEN** a valid unexpired code is verified for its bound tenant, user and purpose
- **THEN** the system consumes the code and returns a short-lived proof that cannot be reused for a different purpose

#### Scenario: Production provider missing
- **WHEN** production SMS verification is requested without valid provider configuration
- **THEN** the request fails without generating or exposing a usable code
