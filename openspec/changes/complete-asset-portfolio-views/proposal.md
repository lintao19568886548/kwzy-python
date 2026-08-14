## Why

The current asset foundation proves spatial hierarchy, current-only unit versions, split/merge lineage and matrix/list rent control, but operators still encode business types as free-form strings and cannot compare vacancy, expiry or operating results. The product contract requires industrial parks, factories, warehouses, shops, offices, dormitories/apartments, parking and public venues to share one rentable-unit model while retaining type-specific attributes and truthful multi-view inventory. The gap blocks capability #3 and makes later CRM, billing and cockpit work depend on ungoverned asset metadata.

## What Changes

- Add tenant-owned asset templates with seven built-in business categories, typed bounded fields, immutable published versions, optimistic administration and database-derived permissions.
- Bind each current unit version to the exact published template version used for validation; structural version, split and merge preserve historical template facts instead of resolving them retroactively.
- Add scoped spatial geometry using bounded GeoJSON point/polygon shapes and an explicit coordinate reference. Geometry is optional, versioned through spatial-node updates and never presented as a procured external GIS/CAD/BIM integration.
- Add map, vacancy, expiry and operating-analysis APIs that reconcile to current inventory, effective lease occupancy and lease dates under the same tenant/park/subtree filters.
- Extend the PC rent-control workspace with template management, matrix/map/list/vacancy/expiry/analysis views, actionable empty/error/permission/conflict states and responsive operation.
- Add PostgreSQL migration, OpenAPI, security/concurrency tests, real HTTP and Playwright journeys, synthetic migration rehearsal and explicit legacy/CAD/BIM disposition.

## Capabilities

### New Capabilities

- `asset-template-governance`: versioned typed asset templates and exact-version unit validation.
- `asset-geospatial-layout`: bounded park-space geometry and truthful map projection without a fake provider claim.
- `rent-control-portfolio-analysis`: reconciled vacancy, expiry and operating portfolio projections.

### Modified Capabilities

- `rentable-unit-versioning`: unit versions retain template/version identity and template-validated attributes through version/split/merge.
- `spatial-hierarchy-management`: spatial nodes may own validated geometry and coordinate reference without weakening hierarchy/scope rules.
- `asset-rent-control-pc`: the real-API workspace gains template, map, vacancy, expiry and analysis modes.
- `asset-data-migration`: legacy factory/floor/type/coordinate metadata receives an explicit mapping/quarantine contract.
- `identity-authorization`: asset-template administration is separated from unit read/write permissions.

## Impact

- Backend: park_property domain/application/repositories/interfaces, lease-backed analysis query and audit.
- Database: forward-only revision after `p2e80a5b7c64`; new template/version tables plus unit and spatial-node references/indexes.
- Frontend: `RentControlView.vue`, typed API state and Playwright flows; no local business JSON.
- Contracts: OpenAPI YAML, strict tests, legacy disposition, synthetic migration evidence and cutover notes.
- External boundary: no production connection, map vendor, CAD/BIM parser or production migration is authorized by this change.
