## 1. Baseline and contract

- [x] 1.1 Inventory current Park/Building/Unit/Lease/WorkOrder models, routes, UI and tests against all six delta specs
- [x] 1.2 Publish old park/factory/factory_floor/rental-manage endpoint disposition and field mapping
- [x] 1.3 Validate the change with `openspec validate implement-asset-rent-control-v2 --strict`

## 2. PostgreSQL schema and migration

- [x] 2.1 Extend buildings with parent, node type, code, ordering, status and attributes
- [x] 2.2 Extend units with logical/version/validity/concurrency/usage/billing/availability fields
- [x] 2.3 Add normalized unit lineage persistence and indexes
- [x] 2.4 Backfill existing buildings and units deterministically without changing lease unit references
- [x] 2.5 Add current-only uniqueness and hierarchy/reference constraints compatible with SQLite and PostgreSQL
- [x] 2.6 Pass Alembic unique-head, fresh base-to-head and one-step down/up checks

## 3. Spatial hierarchy domain and API

- [x] 3.1 Add spatial node entity, mapper and repository with current tenant/park scope
- [x] 3.2 Implement parent-type, same-park, unique-code and cycle rules
- [x] 3.3 Implement hierarchy create, update/move, deactivate and tree query services
- [x] 3.4 Block hierarchy deactivation when active descendants or effective occupancy depend on it
- [x] 3.5 Add transaction-bound sanitized audit records for spatial writes
- [x] 3.6 Add `/spaces` tree/detail/create/update/deactivate APIs and schemas
- [x] 3.7 Add SQLite and PostgreSQL tests for hierarchy validity, concurrency and cross-tenant/park isolation

## 4. Rentable-unit versioning and lineage

- [x] 4.1 Make operational unit repositories current-version-only by default and expose explicit history reads
- [x] 4.2 Remove client `used_area` mutation and validate non-negative area/price/version fields
- [x] 4.3 Implement non-structural edit and versioned structural update with expected-version conflict handling
- [x] 4.4 Implement row-locked split with occupancy guard, exact area reconciliation and atomic lineage
- [x] 4.5 Implement row-locked merge with compatibility guard, exact area reconciliation and atomic lineage
- [x] 4.6 Keep Lease activation/termination occupancy projection correct for current and historical unit references
- [x] 4.7 Map database uniqueness and stale-write conflicts to stable 409 business codes
- [x] 4.8 Add unit history/version/split/merge endpoints, schemas and transaction-bound audits
- [x] 4.9 Add domain/API/PostgreSQL concurrency tests for version, split, merge, rollback and lease races

## 5. Rent-control query model

- [x] 5.1 Implement a shared scoped filter builder for park, spatial subtree, status, usage and keyword
- [x] 5.2 Implement reconciled inventory/area/status/occupancy summary metrics
- [x] 5.3 Implement deterministic paginated list and spatial matrix grouping responses
- [x] 5.4 Implement unit detail with version history, lineage and effective Lease/Party summary
- [x] 5.5 Add related work-order summary when a scoped unit relation exists without leaking foreign data
- [x] 5.6 Add `/rent-control/summary`, `/rent-control/units` and detail APIs
- [x] 5.7 Add reconciliation, zero-denominator, retired-history and cross-scope tests

## 6. PC spatial and rent-control workspace

- [x] 6.1 Replace manual park ID fields with an authorized park selector and real spatial tree
- [x] 6.2 Add summary cards, status/usage filters and matrix/list view switching
- [x] 6.3 Add unit detail drawer with lease/Party, history, lineage and blocking reasons
- [x] 6.4 Add spatial create/edit/move/deactivate forms with validation feedback
- [x] 6.5 Add unit create/edit/version/split/merge flows with expected-version handling
- [x] 6.6 Keep read-only and write controls permission-consistent while relying on server enforcement
- [x] 6.7 Implement loading, empty, error, forbidden and success states
- [x] 6.8 Pass desktop/tablet responsive, visible-focus, semantic-label and keyboard checks

## 7. Migration and compatibility evidence

- [x] 7.1 Implement synthetic asset hierarchy/unit/lineage fixture validation
- [x] 7.2 Implement isolated PostgreSQL first-apply and idempotent re-apply drill
- [x] 7.3 Reconcile node/unit counts, total/rentable/used areas, lineages, orphans and duplicate codes
- [x] 7.4 Prove isolated rollback and add the drill to full local acceptance
- [x] 7.5 Keep real schema/data readiness and production cutover behind explicit human approval

## 8. Contracts and acceptance

- [x] 8.1 Update OpenAPI YAML and runtime contract tests for spatial/version/rent-control APIs
- [x] 8.2 Add Playwright primary path for park selection, hierarchy, matrix/list, detail and vacant split/merge
- [x] 8.3 Add Playwright permission denial, tablet keyboard and failure-state scenarios with no skips
- [x] 8.4 Pass backend full tests, frontend lint/typecheck/unit/build and browser E2E
- [x] 8.5 Pass PostgreSQL migration, asset ETL, backup restore, secrets, diff and OpenSpec strict gates
- [x] 8.6 Update the four controlling rebuild documents with exact commit/report evidence and truthful blockers
- [x] 8.7 Commit and push a clean non-force non-production checkpoint

## Non-goals

Production DB access/deployment, real legacy data migration, GIS/CAD/BIM procurement, employee mobile, tenant mini-program, and unrelated contract/billing/IoT expansion remain outside this change and must not be represented as completed by its local acceptance.
