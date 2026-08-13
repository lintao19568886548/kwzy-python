## Context

### Current Python (main @ 6090c97)

| Surface | Evidence | Status |
|---|---|---|
| `POST /api/v1/auth/login` | `apps/api/app/modules/identity/interface/api.py:17-26` → `AuthService.login` `auth_service.py:21-75` → DB via `AuthorizationRepository` | PARTIAL (real DB) |
| `GET /api/v1/auth/me` | `api.py:29-38` from JWT claims via `get_tenant_context` `deps.py:36-83` | PARTIAL (claim snapshot) |
| Refresh / logout / SMS / page-access | not in identity module | MISSING |
| User/role/menu admin APIs | not present | MISSING |
| Fail-closed auth | `deps.py:47-49` production/staging no anon; anon only `allows_anonymous_dev_identity` | PARTIAL (done for core) |
| `require_permissions` | `deps.py:90-103` | PARTIAL |
| `*` vs all_parks | login claims `auth_service.py:47-59`; park mode from claims `deps.py:20-33` | PARTIAL |

### Old Java Identity/System/Admin (evidence V2.3.2)

Evidence package (portable):

`identity-system-admin-evidence-v2.2` / review ZIP  
Accept: `python accept_identity_review_v2_2.py --package-root .`  
Mother: packaged `inputs/01-java-api-source-inventory-v2.2.csv` (**481**, set equality)

| Metric | Count |
|---|---:|
| Mother scope rows | **481** (set-equal to inventory) |
| INCLUDE_IDENTITY | **74** |
| Controllers INCLUDE | **17** (含 VersionController) |
| Service method RESOLVED | **74** |
| PERSISTENCE_FULLY_RESOLVED | **39** |
| SQL_RESOLVED_PARTIAL | **7** |
| REPOSITORY_METHOD_RESOLVED | **8** |
| SERVICE_METHOD_RESOLVED | **20** |
| Repository call rows 1:N | **169** |
| P0 contracts | **19** (per-endpoint auth/PII/errors) |
| Identity field rows | **52** |
| Source evidence snippets | **422** |
| FE CLOSED | **0** |

**Refresh multi-call sample** (`AuthService.refresh` L617+):

| # | Method | Line | Tables |
|---|---|---:|---|
| 1 | findRefreshToken | 626 | refresh_token |
| 2 | revokeAllUserRefreshTokensAndBumpVersion | 631 | refresh_token\|user |
| 3 | findActiveCenterUserById | 638 | customer\|user |
| 4 | revokeRefreshToken | 645 | refresh_token |
| 5 | persistRefreshToken | 657 | refresh_token |
| 6 | revokeRefreshToken | 662 | refresh_token |

**Scope notes:**

- `VersionController` **INCLUDE** as SYSTEM_ADMIN (`GET /api/system/version`) — restores V1 74-count with explicit reason (not silent whitelist drop).
- `RentalTenantController` / `investment_tenant` **EXCLUDE** as business domain (Party/Investment), not system identity.
- `rental_tenant` table: HUMAN_DECISION_REQUIRED (rental/party subject vs system user).

**Must not regress V2 fixes:** method-level service lines; no param bleed; no keyword FE CLOSED; no fuzzy contracts; no me→Menu; tasks unchecked.

**System admin samples**:

| Controller | Paths (examples) | Lines |
|---|---|---|
| SystemUserController | `GET /api/user/list`, `POST /api/user`, `PUT/DELETE /api/user/{id}` | 27-66 |
| SystemRoleController | `/api/system/role/*` list/create/permissions | 24-87 |
| SystemMenuController | `/api/system/menu/*` | 26-59 |
| MenuController | `GET /api/menu/all` | 19-24 |
| SystemDeptController | `/api/system/dept/*` | 23-43 |
| SystemParkController | system park admin (12 endpoints) | inventory CSV |
| OrganizationController | org + invitation + provisioning (8) | 23-70 |

Frontend old app is **playground** under `<host-path-redacted>` (not a separate unknown repo). Dynamic route components and template URLs remain partially UNRESOLVED in the evidence pack.

### Full-rebuild posture

V2.3.2: `KWZY_FULL_REBUILD_AUDIT_V2_2=CONDITIONAL`; full Java/FE replacement NOT_COMPLETE; data migration BLOCKED. Phase06 Party/Lease/Bill/Payment is scoped COMPLETE only.

## Goals / Non-Goals

**Goals:**

1. Close Identity/System/Admin design so apply can be human-reviewed.
2. Specify authentication, session security, user/role/menu admin, tenant/park grants, audit, legacy mapping, and migration gates.
3. Preserve fail-closed auth and `*` / park-scope orthogonality already on main.
4. Keep evidence line-addressable (no package-scan placeholders as “done”).

**Non-Goals:**

1. Apply / implement code, migrations, or tests in this change cycle.
2. Finance, investment, HRM, meters, bill-import, AI, full frontend rewrite.
3. Production DB access or ETL execution.
4. Unilateral decisions on SMS vendor, multi-DB topology, refresh storage, or PII KMS.

## Decisions

### D1 — Capability split

Identity is split into nine new capabilities plus deltas on `identity-authorization`, `park-scope-model`, and `foundation-compliance`. Rationale: authentication, admin CRUD, menus, sessions, and migration have different risk and approval paths.

### D2 — Layering (apply-time)

```text
Interface (FastAPI routers, schemas)
  → Application services (use-cases)
    → Domain rules (password policy, role invariants)
      → Repository ports
        → Infrastructure (SQLAlchemy, mappers, token store)
```

Entity/Mapper/Repository boundaries follow existing Party/Lease patterns: Application MUST NOT construct ORM models directly.

### D3 — JWT access tokens (snapshot claims)

- Access token remains short-lived JWT with `tenant_id`, `uid`, `permissions`, `park_ids`, `park_scope_mode`.
- Default: **snapshot enforcement** for request path (current `deps.get_tenant_context`).
- Permission admin changes take effect on **re-login** (and refresh if implemented with re-resolve).
- Alternative (DB re-resolve every request) is higher load; only if product demands immediate revoke without denylist.

### D4 — Refresh / logout (decision-gated)

Old Java uses refresh via cookie name `jwt` (`AuthController.java:95-106`) and `AuthService.refresh/logout`.  
Python has **no** refresh yet. Apply MUST NOT invent cookie vs body storage: listed in Open Questions.

Recommended design option for review (not approved):

- Opaque refresh token hashed at rest in PostgreSQL table `refresh_sessions`.
- Rotate on refresh; revoke on logout/password change.
- Access token still JWT.

### D5 — RBAC and park scope

- Action codes on API dependencies (`require_permissions`).
- Menu grants only affect navigation payload.
- Park scope admin writes `user_park_scopes` / `role_park_scopes` / `all_parks` flags (exact table names per ORM).
- `*` never implies ALL parks (existing rule preserved).

### D6 — Password security

- Store only password hashes (current `password_hash` + `verify_password`).
- Migration of legacy hashes: **HUMAN_DECISION_REQUIRED** (algorithm/rounds unknown for all tenants).
- No password in responses/logs/audit detail.

### D7 — SMS / page-access

Legacy endpoints exist (`send-login-code`, `code-login`, page-access). Implementation blocked on vendor + Redis/outbox strategy. Spec keeps capability optional.

### D8 — Legacy compatibility

- Prefer new `/api/v1/...` paths.
- Publish matrix with statuses: EXACT_MATCH / COMPATIBLE_REDESIGN / SCHEMA_MISMATCH / SECURITY_MISMATCH / RESPONSE_MISMATCH / MISSING / HUMAN_DECISION_REQUIRED.
- Current static matrix (evidence pack): login/me ≈ COMPATIBLE_REDESIGN; most admin paths MISSING; some system park paths SCHEMA_MISMATCH vs `/api/v1/parks`.

### D9 — Data migration

- Source: `magic.sql` + Java static SQL only (schema-only).
- Tenant multi-DB production shape unknown → migration readiness stays BLOCKED without dumps.
- PostgreSQL 16 authoritative; SQLite tests secondary.

### D10 — Dept / region / organization

Legacy has SystemDept, SystemRegion, Organization (invites/provisioning).  
**In-scope for evidence and Open Questions**; apply may phase:

- P0: auth session + user/role/permission/park-scope + menu dynamic read  
- P1: menu admin + dept/region if product requires  
- Organization provisioning may belong to tenant-ops change, not forced here

### D11 — Audit

Successful identity admin writes: same-transaction audit like Park/Unit foundation.  
Failed logins: structured logs; durable failure audit optional later.

### D12 — Concurrency / uniqueness

- Username unique per tenant (DB unique constraint).
- Role code unique per tenant.
- Refresh token reuse detection when implemented.
- Admin updates optimistic or last-write-wins with audit (decision at apply).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| JWT snapshot delays permission revoke | Short TTL + refresh re-resolve or denylist (decision) |
| Legacy cookie refresh incompatible | Compatibility adapter only with approved window |
| Password hash migration breaks login | Dual-verify/migrate-on-login design after algorithm decision |
| Org multi-DB provisioning out of identity module | Keep organization endpoints mapped but may defer to tenant-ops |
| Incomplete FE route→component chains | Evidence unresolved list; no silent COMPLETE |
| Over-scoping dept/HR into this change | Explicit phased tasks; human cut line |

## Migration Plan (design only)

1. Freeze field map for users/roles/permissions/scopes/menus from schema-only sources.  
2. Choose hash strategy and tenant topology.  
3. Implement schema migrations on PG16 test DB.  
4. Dry-run row counts and dual-login verification.  
5. Cutover runbook + rollback (restore DB snapshot; feature flag admin APIs).  

**Rollback:** disable new admin routers via config; keep login/me; restore previous Alembic revision only with backup.

## Open Questions

1. Production tenant DB structure vs dev (`magic.sql`) — dumps required?  
2. SMS provider and code storage (Redis vs DB vs outbox)?  
3. Refresh token storage: HttpOnly cookie vs JSON body; rotation policy?  
4. Immediate permission revoke vs snapshot JWT?  
5. Keep legacy menu model compatibility or redesign menus?  
6. Are dept/region/post in this apply phase or later?  
7. Multi-DB org provisioning vs single DB `tenant_id`?  
8. Can legacy password hashes be verified/migrated?  
9. PII encryption/masking and key management?  
10. Legacy `/api/*` retention and deprecation versioning?  
11. Frontend replacement strategy (reuse playground vs new app)?  
12. Should Organization invitation/provisioning stay out of Identity apply?

## Evidence Index (authoritative reads)

- V2.3.2 audit under `kwzy-python-review-artifacts/full-rebuild-gap-audit-v2.2/`
- Identity pack under `kwzy-python-review-artifacts/identity-system-admin-evidence/`
- OpenSpec baselines: `openspec/specs/identity-authorization`, `park-scope-model`, `foundation-compliance`
- Python: `modules/identity/**`, `shared/deps.py`, `core/security.py`
- Java: Auth/System* controllers + AuthService
- Frontend: `playground/src/api/core/**`, system views routers
- SQL: `kwzg-Java-main/magic.sql` (center/partial schema only)


## Evidence package V2.3.2

Design references Identity/System/Admin evidence pack **V2.3.2** (field-level P0/PII, read-only acceptance, final-state source replay). Implementation tasks remain unchecked. IDENTITY_SYSTEM_ADMIN_APPLY=NOT_APPROVED.
