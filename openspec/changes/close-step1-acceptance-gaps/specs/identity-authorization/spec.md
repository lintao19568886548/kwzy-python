## MODIFIED Requirements

### Requirement: JWT claims reflect database authorization without conflating park scope
The system SHALL issue access tokens whose `permissions` represent action permissions only, and whose park data scope is derived independently of the `*` action permission.

#### Scenario: Login embeds independent park scope
- **WHEN** a user logs in successfully
- **THEN** the access token includes `permissions` from RBAC action grants
- **AND** park access is represented by an explicit scope mode and/or park id list that is not inferred solely from `permissions` containing `*`

#### Scenario: Star permission alone does not set all-parks
- **WHEN** a user's only super grant is action permission `*` and the user has no explicit all-parks park-scope grant and no park id list
- **THEN** the resolved park scope is not ALL

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
