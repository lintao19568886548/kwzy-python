# identity-authorization Specification

## Purpose
TBD - created by archiving change harden-step1-foundation. Update Purpose after archive.
## Requirements
### Requirement: Tenant-aware login
The system SHALL resolve an active user within an active SaaS tenant. Login SHALL accept an optional `tenant_code`; when it is omitted and the username exists in more than one tenant, login SHALL reject the request as ambiguous.

#### Scenario: Login with tenant code
- **WHEN** an active user submits valid credentials and the matching tenant code
- **THEN** the system returns an access token whose tenant_id matches that tenant

#### Scenario: Ambiguous username without tenant code
- **WHEN** the same active username exists in multiple active tenants and tenant_code is omitted
- **THEN** the system returns `AUTH_TENANT_AMBIGUOUS` without issuing a token

### Requirement: Database-derived authorization claims
The system SHALL derive action permissions from active user-role and role-permission relationships. The system SHALL derive park data scope independently of action permissions: from explicit all-parks grants (`roles.all_parks` / `users.all_parks` → scope mode ALL) or from the union of active role park scopes and user park scopes (scope mode LIST). The system MUST NOT grant all-park access solely because authentication succeeded, and MUST NOT treat action permission `*` as all-park access.

#### Scenario: Scoped user login
- **WHEN** a user has `park:read` and a scope for park 10
- **THEN** the issued token contains `permissions=["park:read"]` and park scope representing park 10 (LIST) without implying ALL parks

#### Scenario: Explicit administrator login
- **WHEN** a user is assigned an active ADMIN-equivalent role that includes action permission `*` and an explicit all-parks grant
- **THEN** the issued token includes `*` in permissions and represents park scope mode ALL

#### Scenario: Star permission alone does not set all-parks
- **WHEN** a user's only super grant is action permission `*` and the user has no explicit all-parks park-scope grant and no park id list
- **THEN** the resolved park scope is not ALL

#### Scenario: Explicit all-parks grant without star
- **WHEN** a user has an explicit all-parks grant but no `*` action permission
- **THEN** park scope mode is ALL while action permissions remain limited to granted codes

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

### Requirement: Tenant-filtered authorization resolution
Authorization resolution for permissions and park grants SHALL filter all role and scope joins by the authenticated user's `tenant_id`.

#### Scenario: Other tenant role rows ignored
- **WHEN** role_permission or role_park_scope rows exist for another tenant
- **THEN** they are not included in the user's resolved permissions or park scope

### Requirement: Optional tenant_code remains supported
Login SHALL continue to accept optional `tenant_code` to disambiguate same usernames across tenants.

#### Scenario: Ambiguous username without tenant_code
- **WHEN** multiple active tenants contain the same username and no tenant_code is provided
- **THEN** login fails with a tenant ambiguity error

