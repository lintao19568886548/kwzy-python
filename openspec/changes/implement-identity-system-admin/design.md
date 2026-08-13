# Design: Implement Identity / System / Admin

## Context

Existing Python stack: shared PostgreSQL tenant tables, bcrypt passwords, JWT access tokens, park scope modes NONE/LIST/ALL orthogonal to `*` permission.

Legacy Java evidence (V2.3.2): P0 auth/user/role/menu contracts inform behavior; implementation uses modern modular monolith boundaries.

## Goals

- Production-usable admin for users/roles/menus in a single tenant
- Secure session lifecycle (refresh + logout + password change)
- Preserve fail-closed auth and park isolation regressions

## Non-Goals

- Multi-DB center-library topology (ETL later)
- SMS login provider wiring (interface only if needed)
- Full legacy path parity for every Java alias

## Decisions

1. **Refresh tokens** stored hashed in `refresh_tokens` with tenant/user, rotate on use, revoke on logout/password change.
2. **token_version** on users increments on password change; access JWT embeds `tv`; deps reject mismatch when re-resolved (optional soft check on next login cycle first).
3. **Menus** hierarchical (`parent_id`) with route/path/component; roles grant menus via `role_menus`.
4. **Admin APIs** under `/api/v1/system/*` and extend `/api/v1/auth/*`.
5. **Permissions** codes seeded for `identity.user.*`, `identity.role.*`, `identity.menu.*`.

## Risks

- SQLite tests must accept boolean/token_version defaults
- Bootstrap admin must receive new permissions without resetting password

## Migration Plan

- Single Alembic revision after `a7e35f6c8d54`
- Expand bootstrap to seed menu/permissions for default tenant
