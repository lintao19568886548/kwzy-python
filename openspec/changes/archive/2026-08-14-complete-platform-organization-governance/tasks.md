## 1. Evidence and execution control

- [x] 1.1 Record old Java/PC/database evidence and explicit disposition for organization, region, department, park and role-field behavior
- [x] 1.2 Update the master roadmap, agent state and capability matrix with this vertical slice and unchanged external blockers

## 2. Database contract

- [x] 2.1 Add ORM models for groups, regions, effective-dated park assignments, positions, user assignments and field policies
- [x] 2.2 Add one forward Alembic revision after the current head with tenant foreign keys, checks, indexes and uniqueness/concurrency constraints
- [x] 2.3 Register model metadata and verify clean PostgreSQL 16 upgrade, current=heads, downgrade -1 and re-upgrade

## 3. Backend organization governance

- [x] 3.1 Add request/response schemas with enum, length, date and identifier validation
- [x] 3.2 Implement tenant/scope-safe repositories for hierarchy, history, positions, assignments and field policies
- [x] 3.3 Implement group/region lifecycle and atomic park reassignment application services with transactional audit
- [x] 3.4 Implement position lifecycle and effective-dated user assignment services without implicit RBAC or park grants
- [x] 3.5 Implement protected-field registry, fail-closed multi-role policy resolution and server-side user response projection
- [x] 3.6 Mount permission-protected organization governance APIs without Router-to-ORM access
- [x] 3.7 Seed organization-governance and field-policy permission codes idempotently

## 4. PC organization governance workspace

- [x] 4.1 Add typed live-API state and operations for hierarchy, park assignment, positions, user assignments and field policies
- [x] 4.2 Add the system-administration organization-governance tab with real mutation controls and refreshed server state
- [x] 4.3 Add loading, empty, read-only, 403, 409, error/retry, keyboard and responsive states

## 5. API and migration readiness

- [x] 5.1 Update the canonical OpenAPI contract and add contract drift assertions
- [x] 5.2 Publish legacy field/enum/disposition mapping without marking unauthorized old data as migrated
- [x] 5.3 Implement a schema-versioned synthetic ETL drill with dry-run, apply, idempotent rerun, reconcile and rollback

## 6. Automated verification

- [x] 6.1 Add domain/application tests for hierarchy lifecycle, assignment rules and field policy precedence
- [x] 6.2 Add repository/API tests for tenant isolation, park scope, permissions, atomic audit, invalid references and conflicts
- [x] 6.3 Add PostgreSQL 16 tests for one-current-region, one-primary-position and concurrent conflict guarantees
- [x] 6.4 Add real HTTP smoke covering the complete organization governance journey and server-side phone masking
- [x] 6.5 Add Playwright desktop/tablet/mobile journeys including read-only, conflict and retry behavior
- [x] 6.6 Capture key PC screenshots and classify visual results against the design system

## 7. Closure and delivery

- [x] 7.1 Run focused backend/frontend tests, type checks, build, migration drill and strict OpenSpec validation
- [x] 7.2 Run the full acceptance suite on PostgreSQL 16 and update evidence, capability matrix, roadmap and agent state with exact results
- [x] 7.3 Commit the complete vertical slice and normally push `feat/full-rebuild-completion` without force
