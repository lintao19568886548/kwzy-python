## MODIFIED Requirements

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

## ADDED Requirements

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
