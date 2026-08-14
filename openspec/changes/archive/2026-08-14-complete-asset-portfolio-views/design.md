## Context

`buildings` is the compatible physical table for AREA/BUILDING/FLOOR nodes and `units` stores immutable structural versions. Lease occupancy is authoritative and existing matrix/list queries are tenant/park scoped. Asset category is currently a free string and `attributes_json` has no schema. The old Java application has factory/floor forms with ad-hoc facility fields and image/map helpers, but no reliable shared asset-template aggregate or proven GIS/CAD/BIM contract.

## Goals / Non-Goals

**Goals**

- Publish deterministic template versions for FACTORY, WAREHOUSE, SHOP, OFFICE, DORMITORY, PARKING and PUBLIC_SPACE categories.
- Validate unit attributes on the server and retain the exact template version in every historical unit row.
- Store bounded, safe GeoJSON Point/Polygon geometry on spatial nodes and expose a scoped FeatureCollection.
- Reconcile vacancy, upcoming expiry and operating metrics with current units and effective leases.
- Deliver real PC interactions, PG16 constraints/concurrency, HTTP/E2E and reversible synthetic migration evidence.

**Non-goals**

- Procuring a commercial basemap, geocoder, CAD/BIM authoring system or digital twin.
- Claiming external coordinates or old production data are migrated without authorized schema/sample evidence.
- Rebuilding lease, billing, CRM, mobile or mini-program domains in this change.

## Decisions

### D1 — Template aggregate with immutable published versions

`AssetTemplate` owns tenant-unique code, category, status and optimistic lock. `AssetTemplateVersion` owns a positive version, DRAFT/PUBLISHED/RETIRED status, typed field schema and defaults. Published rows never mutate; editing creates or updates a draft. The unit references `asset_template_version_id`, so later template publication cannot rewrite history.

### D2 — Bounded declarative field grammar

Fields are an ordered JSON array with allow-listed `key`, `label`, `type` (`TEXT`, `NUMBER`, `BOOLEAN`, `ENUM`), required flag, optional unit/min/max/options and a maximum of 32 fields. Keys and enum values are bounded scalars; nested schemas, expressions, URLs and executable content are rejected. Unit attributes reject unknown keys and invalid values.

### D3 — Built-ins are tenant materialized, not global hidden defaults

An idempotent bootstrap command creates seven editable tenant-owned templates. It never invents units or overwrites existing codes. Creation can also lazily ensure built-ins for a new tenant. Listing and unit creation use persisted published versions only.

### D4 — Spatial geometry is truthful and provider-neutral

Spatial nodes receive optional `geometry_json`, `geometry_type`, `coordinate_reference` and `geometry_version`. Only GeoJSON Point or simple Polygon is accepted, coordinate counts and ranges are bounded, rings must close, and arbitrary properties are discarded. `/rent-control/map` returns a FeatureCollection using stored coordinates plus current unit/status aggregates. Missing geometry is explicitly reported as unmapped inventory, never rendered at invented coordinates.

### D5 — Analysis derives from source records

`/rent-control/analysis` groups current units by template category, usage type, status and space; revenue potential uses current base rent × available area only as an explicitly labelled asking-rent potential, not booked revenue. `/rent-control/vacancies` returns current available inventory and vacancy days from `available_from`. `/rent-control/expiries` derives upcoming effective lease end dates and source contract/unit IDs. All projections share the existing scoped filter builder.

### D6 — Template binding is structural

Changing template or template-governed attributes creates a new unit version. Split inherits the source template unless a target explicitly selects another compatible published version; merge requires one shared template version unless an explicit target version is supplied and every resulting attribute validates. Source rows remain untouched.

### D7 — Separate administration permission

Reads use `asset.template.read`; mutation/publication uses `asset.template.write`. Unit permissions do not grant template administration. Unit read responses may expose only the public template code/name/version and validated attributes.

### D8 — PC uses a schematic SVG map when geometry exists

The map view projects stored normalized/local coordinates into an SVG viewport, with accessible feature buttons and the same detail drawer. It labels the coordinate reference and unmapped count. This is a real geometry view, not a screenshot, static chart or claim of live GIS.

## Risks / Trade-offs

- JSON field schemas are less queryable than EAV columns; bounded validation plus exact-version references avoids schema sprawl while preserving history.
- Local coordinates cannot be overlaid on public basemaps; explicit CRS and provider-neutral GeoJSON prevent false precision.
- Asking-rent potential is not accounting revenue; API/UI naming and reconciliation tests keep the distinction visible.
- Existing units lack template references; migration/backfill maps known usage types to persisted built-ins during the isolated rehearsal and application bootstrap, while unknown values are quarantined rather than guessed.

## Migration Plan

1. Add template/version tables and nullable unit/spatial geometry fields in a new forward revision; backfill only safe structural defaults.
2. Deploy idempotent tenant template bootstrap and compatibility reads; existing units without a template remain readable but new structural writes require a published version.
3. Run synthetic dry/apply/interruption/reapply/reconcile/rollback against PG16 and verify no production target/provider use.
4. Enable template/map/analysis endpoints and PC views after authorization seeds and OpenAPI checks.
5. Real legacy migration remains blocked until an authorized schema and desensitized asset sample are supplied.

Rollback after business writes is application rollback plus a forward repair; historical template/unit/geometry evidence must not be deleted.
