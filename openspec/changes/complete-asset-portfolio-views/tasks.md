## 1. Evidence and contract

- [x] 1.1 Record old factory/floor/type/facility/map evidence and explicit replace/retain/block disposition
- [x] 1.2 Define built-in categories, bounded field grammar, geometry semantics and analysis formulas
- [x] 1.3 Update capability matrix and cutover/migration boundary without claiming CAD/BIM or real-data completion

## 2. Persistence and migration

- [x] 2.1 Add pure-domain template/version and geometry value contracts
- [x] 2.2 Add tenant-safe ORM tables, unit template reference, geometry fields, constraints and indexes
- [x] 2.3 Add one forward Alembic revision after `p2e80a5b7c64` without editing history
- [x] 2.4 Verify PG16 fresh upgrade, current=heads, downgrade -1/up and ORM parity

## 3. Template governance

- [x] 3.1 Implement idempotent seven-category tenant bootstrap
- [x] 3.2 Implement tenant-scoped repositories and list/detail/create/update-draft/publish/new-draft/retire lifecycle
- [x] 3.3 Validate bounded field schemas/defaults and immutable published versions
- [x] 3.4 Validate unit attributes and exact published template binding on create/version/split/merge
- [x] 3.5 Record transaction-bound audit and database-derived template permissions

## 4. Map and analysis queries

- [x] 4.1 Validate Point/Polygon geometry, CRS, coordinate bounds, size and optimistic version
- [x] 4.2 Implement scoped GeoJSON FeatureCollection with per-space current unit/status aggregates and unmapped counts
- [x] 4.3 Implement vacancy projection with duration, availability and deterministic pagination
- [x] 4.4 Implement upcoming expiry projection from effective leases with source IDs and stable date windows
- [x] 4.5 Implement category/status/space operating analysis and asking-rent potential reconciliation
- [x] 4.6 Add query/index bounds and no cross-tenant/park relation leakage

## 5. API and OpenAPI

- [x] 5.1 Add template lifecycle schemas/routes with separate read/write permissions
- [x] 5.2 Extend unit and spatial schemas with template/geometry/version fields
- [x] 5.3 Add map, vacancies, expiries and analysis routes with bounded filters/page sizes
- [x] 5.4 Update runtime and YAML OpenAPI plus strict contract tests

## 6. PC asset workspace

- [x] 6.1 Add live template state and administration drawer with published-readonly/409/403 states
- [x] 6.2 Add matrix/map/list/vacancy/expiry/analysis view switch using real APIs
- [x] 6.3 Render accessible schematic geometry, CRS and unmapped inventory without fake basemap claims
- [x] 6.4 Add template-aware unit forms and typed dynamic attributes
- [x] 6.5 Add loading/empty/error/offline/retry/permission/conflict states at desktop/tablet/mobile widths

## 7. Migration readiness

- [x] 7.1 Publish legacy asset-template/facility/coordinate field mapping and quarantine reasons
- [x] 7.2 Implement synthetic dry/apply/interruption/idempotent/reconcile/rollback on test-only PG target
- [x] 7.3 Reconcile template counts, unit bindings, geometry, area/status/lease facts and prove no raw PII/provider calls

## 8. Automated verification

- [x] 8.1 Add template grammar/lifecycle/immutability and unit-binding tests
- [x] 8.2 Add tenant/park/permission/IDOR/parameter-pollution and geometry rejection tests
- [x] 8.3 Add PG16 unique/concurrent publish, stale geometry and unit-version tests
- [x] 8.4 Add analysis source-record reconciliation, pagination and query-bound tests
- [x] 8.5 Add real HTTP template→space geometry→unit→map/vacancy/expiry/analysis journey
- [x] 8.6 Add Playwright multi-view/admin/read-only/409/offline desktop/tablet/mobile journeys and screenshots

## 9. Closure

- [x] 9.1 Run focused backend/frontend tests, Ruff, typecheck/build, strict OpenSpec and targeted stub/layer scans
- [ ] 9.2 Run full PG16 acceptance, backup/restore, performance and clean-SHA browser evidence
- [ ] 9.3 Update reports/matrix/roadmap/state, normally commit/push, sync main specs and archive without force
