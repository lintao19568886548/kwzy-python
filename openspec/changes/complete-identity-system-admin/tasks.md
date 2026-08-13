## 0. Planning boundary (this change cycle)

- [ ] 0.1 Confirm this change is design-only: no `openspec apply`, no business code, no Alembic, no production DB
- [ ] 0.2 Confirm evidence pack exists under `review-artifacts/identity-system-admin-evidence/`
- [ ] 0.3 `openspec validate complete-identity-system-admin --strict` passes
- [ ] 0.4 Human review of proposal/design/specs/tasks and Open Questions
- [ ] 0.5 Explicit written approval before any apply branch is created

**Gate:** `IDENTITY_SYSTEM_ADMIN_APPLY=NOT_APPROVED` until 0.5 is satisfied by a human.

---

## 1. Evidence closure

> V2.2: portable package, 481 set-equality scope, source-evidence snapshots, multi-repo call_kind, P0 per-endpoint security/PII/errors.  
> **Evidence PASS ≠ apply.** All items remain unchecked.

- [ ] 1.1 Raise PERSISTENCE_FULLY_RESOLVED for remaining SERVICE_ONLY / REPO_METHOD / SQL_PARTIAL endpoints
- [ ] 1.2 Expand RoleWritePermissionService path matrix evidence beyond AuthFilter.canWrite gate
- [ ] 1.3 FE call-graph coverage for desktop login/role/menu without keyword binding
- [ ] 1.4 Dynamic component HUMAN_REQUIRED register
- [ ] 1.5 Complete BusinessException code catalog per P0 method (already partial for auth)
- [ ] 1.6 Field map + tenant schema-only dumps; migration stays BLOCKED
- [ ] 1.7 Re-run `accept_identity_review_v2_2.py --package-root .` after any evidence change
- [ ] 1.8 Product decisions: rental_tenant, Organization vs tenant-ops, refresh cookie compatibility

---

## 2. Domain and application design

- [ ] 2.1 Domain model: User, Role, Permission, Menu, grants, park scopes, session/refresh (if approved)
- [ ] 2.2 Use-cases list for authentication and admin services
- [ ] 2.3 Permission code catalog and naming convention
- [ ] 2.4 Menu vs action permission rules finalized
- [ ] 2.5 Token claim schema document (access + optional refresh)
- [ ] 2.6 Decision log answers for Open Questions that block apply

---

## 3. Database and migration design

- [ ] 3.1 Target PostgreSQL 16 tables/indexes/constraints design (users/roles/permissions/menus/scopes/sessions)
- [ ] 3.2 Alembic migration plan (not executed in design cycle)
- [ ] 3.3 SQLite semantic differences checklist for tests
- [ ] 3.4 Identity field mapping review with transform rules (password hash decision)
- [ ] 3.5 Tenant topology decision (single DB vs multi DB) recorded
- [ ] 3.6 ETL readiness remains BLOCKED without tenant schema-only dumps

---

## 4. Authentication / session implementation (apply only)

- [ ] 4.1 Keep/extend password login with tenant disambiguation
- [ ] 4.2 Implement refresh/logout/revoke per approved design
- [ ] 4.3 Password change + admin reset with session revoke
- [ ] 4.4 Optional SMS/page-access only after provider decision
- [ ] 4.5 Preserve production fail-closed; no anon in production/staging

---

## 5. User / role / menu administration (apply only)

- [ ] 5.1 User list/create/update/disable APIs + permissions
- [ ] 5.2 Role CRUD + permission bind/unbind
- [ ] 5.3 Menu admin + dynamic menu for current user
- [ ] 5.4 Dept/region only if phase decision includes them
- [ ] 5.5 OpenAPI updates for all new routes

---

## 6. Authorization and scope enforcement (apply only)

- [ ] 6.1 Park scope grant APIs for user/role + all_parks
- [ ] 6.2 Enforce require_permissions on all admin writes/reads as designed
- [ ] 6.3 Confirm `*` does not imply all parks (regression tests)
- [ ] 6.4 Cross-tenant isolation tests for admin resources
- [ ] 6.5 Document snapshot JWT vs re-resolve behavior in runtime docs

---

## 7. Audit and security hardening (apply only)

- [ ] 7.1 Audit successful identity admin writes
- [ ] 7.2 Ensure no password/hash/token secrets in responses, logs, audit detail
- [ ] 7.3 Failed login observability
- [ ] 7.4 Security tests for anon/dev bypass absent in production
- [ ] 7.5 Rate limits for login/SMS if SMS enabled

---

## 8. Legacy compatibility (apply only)

- [ ] 8.1 Publish endpoint compatibility matrix with contract_status enums
- [ ] 8.2 Implement only approved shims/aliases
- [ ] 8.3 Deprecation timeline documentation
- [ ] 8.4 No EXACT_MATCH without schema proof

---

## 9. Tests (apply only)

- [ ] 9.1 Unit/domain tests for identity rules
- [ ] 9.2 API tests SQLite for admin CRUD and auth
- [ ] 9.3 PostgreSQL tests for uniqueness, scopes, sessions
- [ ] 9.4 Security tests fail-closed + permission matrix
- [ ] 9.5 OpenAPI contract tests updated
- [ ] 9.6 Regression: Party/Lease/Bill/Payment still pass

---

## 10. Documentation and acceptance (apply only)

- [ ] 10.1 Update docs/06-implementation for identity admin
- [ ] 10.2 Acceptance checklist vs Open Questions closure
- [ ] 10.3 Record remaining MISSING legacy endpoints explicitly
- [ ] 10.4 Re-state full rebuild still NOT_COMPLETE after identity apply
- [ ] 10.5 Archive change only after human acceptance

---

## Explicit non-tasks (do not do in this design cycle)

- [ ] N1 ~~openspec apply~~ **FORBIDDEN now**
- [ ] N2 ~~Write production business code~~ **FORBIDDEN now**
- [ ] N3 ~~Run Alembic on shared/prod DBs~~ **FORBIDDEN**
- [ ] N4 ~~Connect old Java production DB~~ **FORBIDDEN**
- [ ] N5 ~~git commit/push/merge main for apply~~ **FORBIDDEN without separate approval**
