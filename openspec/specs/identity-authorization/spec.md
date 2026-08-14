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

### Requirement: Database-derived organization governance permissions
The system SHALL authorize organization hierarchy, position assignment, and field policy operations using current-tenant database role permissions and MUST ignore client-declared role, permission, or field access claims.

#### Scenario: Fabricated permission rejected
- **WHEN** a client without `identity.org_governance.write` submits a write request and declares that permission in the request body or header
- **THEN** the system returns forbidden and persists no business or success audit row

#### Scenario: Revoked permission takes effect through session controls
- **WHEN** an administrator removes an organization governance permission from a role
- **THEN** affected sessions are invalidated under the existing token-version policy and subsequent writes are denied

### Requirement: Database-derived approval and audit permissions
The system SHALL authorize approval definition read/write, task read/decision, delegation management, audit read and audit export using current-tenant database role permissions and MUST ignore client-declared permissions, roles, assignees or audit scopes.

#### Scenario: Fabricated decision permission rejected
- **WHEN** a client without `approval.task.decide` declares that permission in a header or body and submits a decision
- **THEN** the system returns forbidden and persists no task, event, work-item, business or success-audit transition

#### Scenario: Audit export separated from read
- **WHEN** a role has `audit.read` but not `audit.export`
- **THEN** the user can search scoped rows but cannot export them

### Requirement: Approval override is explicit and auditable
Self-approval override SHALL require the database-derived `approval.task.override_self` permission plus a non-empty reason, and SHALL record both the normal decision event and a high-risk override audit summary.

#### Scenario: Star permission still requires reason
- **WHEN** a super-permission user self-approves without an override reason
- **THEN** the command is rejected and no approval transition commits

### Requirement: Workbench automation permission separation
The system SHALL seed and enforce distinct permissions for personal layout configuration, role layout administration, notification access, automation rule read/write, scheduler read/run/write and event dead-letter replay.

#### Scenario: Layout editor lacks scheduler permission
- **WHEN** a caller can configure their workbench but cannot operate schedules
- **THEN** layout commands succeed while scheduler definitions and runs remain forbidden

#### Scenario: Client claim bypass attempt
- **WHEN** a valid token contains an automation permission absent from current database grants
- **THEN** protected automation operations remain forbidden
