## ADDED Requirements

### Requirement: Tenant-aware login
The system SHALL resolve an active user within an active SaaS tenant. Login SHALL accept an optional `tenant_code`; when it is omitted and the username exists in more than one tenant, login SHALL reject the request as ambiguous.

#### Scenario: Login with tenant code
- **WHEN** an active user submits valid credentials and the matching tenant code
- **THEN** the system returns an access token whose tenant_id matches that tenant

#### Scenario: Ambiguous username without tenant code
- **WHEN** the same active username exists in multiple active tenants and tenant_code is omitted
- **THEN** the system returns `AUTH_TENANT_AMBIGUOUS` without issuing a token

### Requirement: Database-derived authorization claims
The system SHALL derive permissions from active user-role and role-permission relationships, and SHALL derive park_ids from the union of active role park scopes and user park scopes. The system MUST NOT grant `*` solely because authentication succeeded.

#### Scenario: Scoped user login
- **WHEN** a user has `park:read` and a scope for park 10
- **THEN** the issued token contains `permissions=["park:read"]` and `park_ids=[10]` without `*`

#### Scenario: Explicit administrator login
- **WHEN** a user is assigned an active role containing the `*` permission
- **THEN** the issued token grants explicit all-park access

### Requirement: Permission-protected Park and Unit APIs
The system SHALL enforce action permission codes independently from tenant and park data scope. Users without the required code MUST receive a 403 envelope.

#### Scenario: Write without permission
- **WHEN** an authenticated scoped user calls a Park or Unit write endpoint without the corresponding write permission
- **THEN** the system returns 403 with code `PERMISSION_DENIED`

#### Scenario: Permission and park scope both allow action
- **WHEN** the user has the required action permission and the target park is in park_ids
- **THEN** the request proceeds to the application service

### Requirement: Production authentication requirement
The system SHALL require a valid JWT in production. Local and test environments MAY use the explicit development super-scope fallback.

#### Scenario: Production request without token
- **WHEN** APP_ENV is production and a protected endpoint is called without a bearer token
- **THEN** the system returns 401 with code `UNAUTHORIZED`
