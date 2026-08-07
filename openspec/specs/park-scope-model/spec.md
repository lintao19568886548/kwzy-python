# park-scope-model Specification

## Purpose
TBD - created by archiving change close-step1-acceptance-gaps. Update Purpose after archive.
## Requirements
### Requirement: Action permissions are independent of park data scope
A permission code of `*` SHALL grant all **action** permissions only. It SHALL NOT by itself grant access to all parks' data.

#### Scenario: Star action without park scope is not all-parks
- **WHEN** a user has action permission `*` and park scope mode is not ALL and has no listed parks
- **THEN** action checks for protected routes may pass for `*`, but park-scoped data access is denied (empty list and/or not-found/forbidden on foreign parks)

### Requirement: Explicit all-parks authorization
All-parks data access SHALL be granted only through an explicit park-scope authorization (for example `park_scope_mode=ALL` derived from `user.all_parks` or `role.all_parks`), not from action permission codes alone.

#### Scenario: Explicit all-parks allows any park in tenant
- **WHEN** the user's resolved park scope mode is ALL within their tenant
- **THEN** repository park filters allow access to parks of that tenant without requiring each park id in a list

### Requirement: Listed park scope
When park scope mode is LIST, access SHALL be limited to the union of authorized park ids.

#### Scenario: Only listed parks visible
- **WHEN** park scope mode is LIST with parks {A}
- **THEN** resources in park B are not readable or writable by that user

### Requirement: Empty park scope denies by default
When park scope mode is NONE (or LIST with empty ids), the user SHALL NOT receive all-parks access.

#### Scenario: Empty scope denies
- **WHEN** the user has no all-parks grant and an empty park id set
- **THEN** park-scoped list endpoints return no other users' parks data for that user and park-targeted writes fail authorization/data-scope checks

### Requirement: Merge rules for user and role park grants
Resolved park ids SHALL be the union of the user's direct park grants and the park grants of the user's active roles, all filtered by the same `tenant_id` as the user.

#### Scenario: Union of direct and role parks
- **WHEN** user has direct park A and a role grants park B in the same tenant
- **THEN** resolved LIST scope includes both A and B

#### Scenario: Cross-tenant role bindings are ignored
- **WHEN** a role_permission or role_park row exists with a different tenant_id than the user
- **THEN** authorization resolution does not include that row

### Requirement: ADMIN seed compatibility
Default ADMIN bootstrap SHALL grant explicit all-parks authorization for local/test admin in addition to action super-permission, so local administrators retain operational access after the separation change.

#### Scenario: Seeded admin retains all-parks via explicit grant
- **WHEN** local/test bootstrap completes successfully
- **THEN** the ADMIN principal is authorized for all parks through the explicit park-scope mechanism, not merely because action permission is `*`

