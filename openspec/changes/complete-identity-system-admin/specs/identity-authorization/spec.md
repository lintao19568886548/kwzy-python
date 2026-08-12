## MODIFIED Requirements

### Requirement: Database-derived authorization claims
The system SHALL derive action permissions from active user-role and role-permission relationships. The system SHALL derive park data scope independently of action permissions: from explicit all-parks grants (`roles.all_parks` / `users.all_parks` → scope mode ALL) or from the union of active role park scopes and user park scopes (scope mode LIST). The system MUST NOT grant all-park access solely because authentication succeeded, and MUST NOT treat action permission `*` as all-park access. When identity administration APIs change role or park grants, the system SHALL document whether existing access tokens keep snapshot claims until expiry or require re-login/refresh; the default design assumption is JWT snapshot until refresh/re-login unless a re-resolve decision is approved.

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

#### Scenario: Admin grant change does not silently rewrite existing JWT mid-request
- **WHEN** an admin removes a permission from a role while a bearer token still contains the old permission claim
- **THEN** the system either continues snapshot enforcement until token expiry/refresh or re-resolves from DB only if that policy is explicitly enabled and tested

## ADDED Requirements

### Requirement: Identity administration APIs require permission codes
User, role, menu, and park-scope administration endpoints SHALL declare and enforce action permission codes via the same `require_permissions` mechanism used by business modules.

#### Scenario: Role create without permission
- **WHEN** an authenticated user without role-manage permission calls role create
- **THEN** the system returns 403 `PERMISSION_DENIED`
