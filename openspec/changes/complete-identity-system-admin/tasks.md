## 0. Reconcile planning and authority

- [x] 0.1 Record the current main@d9c0b0b implementation baseline instead of the obsolete main@6090c97 baseline
- [x] 0.2 Record the user's explicit unattended apply/commit/push authorization and preserve production/external credential gates
- [x] 0.3 Audit current Identity backend, PC page, tests, migrations, routes and data models against all twelve delta specs
- [x] 0.4 Pass `openspec validate complete-identity-system-admin --strict` after the planning rewrite

## 1. Existing implementation verified on main

- [x] 1.1 Tenant-disambiguated password login derives permissions and park scope from database relationships
- [x] 1.2 Fail-closed Bearer authentication is enforced outside explicit local/test anonymous mode
- [x] 1.3 Opaque refresh tokens are hashed at rest, rotated on refresh and rejected after logout
- [x] 1.4 Self-service password change updates the hash, increments token_version and revokes refresh tokens
- [x] 1.5 Tenant-scoped user list/create/update/disable and role/park assignment APIs exist
- [x] 1.6 Tenant-scoped role list/create/update with permission/park/menu assignments exists
- [x] 1.7 Permission catalog, menu list/create and current-user dynamic menu APIs exist
- [x] 1.8 Organization, dictionary and masked system-parameter APIs exist
- [x] 1.9 PC System Admin route and basic CRUD E2E exist
- [x] 1.10 PostgreSQL identity/session/menu migration and baseline session/admin tests exist

## 2. Session and authentication hardening

- [x] 2.1 Validate active user, tenant ownership and token_version on every protected request
- [x] 2.2 Make user disable and administrative password reset increment token_version and revoke all refresh sessions
- [x] 2.3 Increment affected users' token_version and revoke refresh sessions after role permission, role scope or role status changes
- [x] 2.4 Make refresh rotation concurrency-safe and revoke the session family on reuse of a rotated token
- [x] 2.5 Add shared PostgreSQL login rate limiting keyed by tenant/account digest and client IP
- [x] 2.6 Add sanitized security-event evidence for failed login, refresh reuse and rate-limit decisions
- [x] 2.7 Support HttpOnly SameSite refresh cookie for PC while preserving response-body refresh for mobile clients
- [x] 2.8 Remove PC refresh-token persistence from localStorage and cover refresh/logout cookie behavior

## 3. Verification code and page-access proof

- [x] 3.1 Add hashed, expiring, one-time verification code and page-access proof persistence
- [x] 3.2 Add provider-neutral send and verify application services with purpose/user/tenant binding
- [x] 3.3 Route sends through SMS provider/outbox and keep production fail-closed when credentials are absent
- [x] 3.4 Enforce send/verify rate limits, attempt caps, expiry and one-time consumption
- [x] 3.5 Add local/test fake-provider tests without returning codes from production API responses

## 4. Identity administration completeness

- [x] 4.1 Add menu update and deactivate APIs with parent-cycle and tenant validation
- [x] 4.2 Validate every role, park and menu reference belongs to the caller tenant before assignment
- [x] 4.3 Map uniqueness and concurrent-write violations to stable 409 business errors
- [x] 4.4 Record transaction-bound audits for user, role, menu and park-scope administration writes
- [x] 4.5 Add user/session administrative revoke endpoint with explicit elevated permission
- [x] 4.6 Add focused cross-tenant, forbidden, invalid-reference and audit-redaction API tests

## 5. PC system administration experience

- [x] 5.1 Replace comma-separated permission input with permission catalog selection
- [x] 5.2 Add explicit ALL/LIST/NONE park-scope controls and remove hard-coded all_parks=true
- [x] 5.3 Add user role/park assignment and user edit/enable/disable/reset-session flows
- [x] 5.4 Add role permission/park/menu edit and role deactivate flows
- [x] 5.5 Add menu create/edit/deactivate hierarchy management
- [x] 5.6 Prove route visibility, button visibility and direct API denial are consistent but independently enforced
- [x] 5.7 Meet desktop/tablet responsive and accessibility checks for the system admin surface

## 6. Legacy compatibility and migration evidence

- [x] 6.1 Publish the 74-row Identity/System/Admin legacy endpoint disposition matrix with target route and reason
- [x] 6.2 Publish source-to-target user/role/permission/menu/scope/session field mapping with transform rules
- [x] 6.3 Implement synthetic Identity ETL dry-run/apply/idempotency/rollback and reconciliation checks
- [ ] 6.4 Obtain and verify read-only tenant schema dumps before changing real migration readiness from BLOCKED
- [ ] 6.5 Decide and prove legacy password hash verification or controlled reset using authorized samples
- [x] 6.6 Keep production cutover, real SMS and legacy deprecation window behind explicit human approval

## 7. Acceptance and documentation

- [x] 7.1 Pass focused Identity unit/API tests on SQLite and PostgreSQL 16
- [x] 7.2 Pass Alembic unique-head, base-to-head and one-step down/up checks for new schema
- [x] 7.3 Pass PC Playwright system-admin and authentication/session scenarios with no skips
- [x] 7.4 Update OpenAPI/YAML contracts and pass strict contract validation
- [x] 7.5 Update the four controlling rebuild documents with exact commit/test evidence and truthful blockers
- [x] 7.6 Pass lint, typecheck, build, secrets scan and `openspec validate --all --strict`
- [x] 7.7 Commit and push a clean non-force checkpoint; do not deploy production

## Non-goals for this change

- Production database access, production cutover or irreversible production operations.
- Real SMS/WeChat/KMS credential acquisition or vendor commercial decisions.
- Tenant provisioning/invitation, HRM, finance, IoT or unrelated business-domain implementation.
- Treating fake adapters, synthetic fixtures or local staging-equivalent tests as live production evidence.
