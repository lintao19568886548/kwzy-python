## Why

The current Python system has no mounted device registry, periodic inspection or IoT alarm capability, while the legacy system stores fire, elevator, transformer, hygiene and building-maintenance rows as separate string-heavy CRUD tables with physical deletion and unsafe unauthenticated registration. The rebuild needs one tenant/park-scoped facility model that preserves evidence, creates governed field tasks and turns verified exceptions into the already implemented WorkOrder lifecycle without pretending that an external IoT provider is connected.

## What Changes

- Add a versioned facility device registry for fire, elevator, transformer, electrical, HVAC, water, security and custom device types, including park/unit/location ownership, lifecycle status, criticality, service dates and immutable history.
- Add structured inspection templates, published versions, weekly-capable schedules, deterministic task generation, assignment, execution evidence and missed-task escalation.
- Add checklist-level results with numeric/text/boolean bounds; failed critical checks create one linked exception and one governed WorkOrder without duplicate side effects.
- Add IoT provider and device-binding truth records whose runtime status distinguishes `NOT_CONNECTED`, `SANDBOX`, `CONNECTED` and `DEGRADED`; production configuration fails closed when required credentials are absent.
- Add signed and replay-safe alarm ingestion, source-event deduplication, severity normalization, correlation windows, acknowledgement, escalation and closure. Repeated events update one alarm occurrence count and do not fabricate provider delivery.
- Add alarm-to-WorkOrder linkage with deterministic severity policy, optimistic concurrency, tenant/park isolation, append-only events, WorkItems, notifications and audit.
- Add live PC device/inspection/alarm workspaces with role-aware actions, queue/KPI drill-down, conflict/offline/retry and desktop/tablet/mobile-width evidence. This does not create the independent employee app or tenant mini-program.
- Add PostgreSQL constraints/concurrency tests, exact runtime/YAML OpenAPI, synthetic legacy maintenance/IoT migration rehearsal, real HTTP/browser/performance/backup evidence and explicit live-provider blockers.
- Do not copy legacy physical deletion or anonymous default-tenant write semantics; retirement/cancellation and authenticated one-time inspection access are evidence-preserving replacements.

## Capabilities

### New Capabilities

- `facility-device-registry`: Tenant/park-scoped device master data, lifecycle, ownership, history and controlled retirement.
- `inspection-template-schedule`: Versioned checklist templates, published weekly schedules and deterministic repeat-safe task generation.
- `inspection-execution-exception`: Assigned inspection execution, structured results/evidence, missed/failed exceptions and WorkOrder linkage.
- `iot-provider-device-binding`: Truthful provider registry, fail-closed runtime configuration and tenant/park/device bindings.
- `iot-alarm-lifecycle`: Authenticated ingestion, deduplication/correlation, severity, acknowledgement/escalation/closure and linked WorkOrders.
- `facility-ops-api`: Strict staff/field APIs, scope inheritance, idempotency, optimistic concurrency and exact OpenAPI contract.
- `facility-ops-pc`: Live responsive device, inspection and alarm workspace with accessible status and actionable error states.
- `facility-ops-data-migration`: Versioned legacy maintenance/device mapping, quarantine, idempotent rehearsal, reconciliation and real-cutover blockers.

### Modified Capabilities

- None. WorkOrders remain the downstream remediation aggregate through their existing governed API/service contract; external platform live verification remains independently tracked.

## Impact

- Backend: new FacilityOps domain rules, SQLAlchemy models/repository/application services, mounted FastAPI routes, permissions, outbox/WorkItem/audit integration and forward-only Alembic revisions after `y1b79d4e6f53`.
- Database: new device, device-history, inspection template/version/item/schedule/task/result/exception, provider/binding, alarm/event/correlation tables with composite tenant/park foreign keys, partial uniques and concurrency controls.
- PC: new facility operations route/view and real HTTP Playwright journeys; existing global navigation, role bootstrap and seed data are extended.
- Contracts/data: checked-in OpenAPI additions, legacy disposition, field mapping, synthetic fixtures/drills and versioned acceptance/visual evidence.
- External systems: no production IoT endpoint is contacted. Local/sandbox verification and fail-closed adapters are delivered; real vendors, credentials, callbacks and production cutover remain `NOT_CONNECTED`/`BLOCKED_EXTERNAL_EVIDENCE` until supplied and authorized.
