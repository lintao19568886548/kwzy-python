# Change: Implement Identity / System / Admin

## Why

Design/evidence (`complete-identity-system-admin` + V2.3.2 pack) is ready for human review, but runtime still only has login/me. Users cannot administer accounts, roles, menus, or rotate sessions—blocking full Java replacement and secure multi-park ops.

## What Changes

- Session: refresh token rotation, logout revoke, password change with token version bump
- User lifecycle: list/create/update/disable within tenant + park grants
- Role lifecycle: list/create/update + permission bind
- Menu: tenant menu tree + role-menu grants + current-user route menus
- Authorization: keep fail-closed JWT + park scope; `*` is actions only, not all parks
- Alembic migration for refresh_tokens, menus, role_menus, users.token_version
- Tests covering auth flows and admin isolation

## Impact

- Affected specs: identity-authentication, identity-authorization, user-lifecycle, role-permission, menu-page-access, token-session-security, foundation-compliance
- Affected code: `apps/api/app/modules/identity/**`, models, alembic, tests
- Does **not** execute production ETL or SMS/payment providers
