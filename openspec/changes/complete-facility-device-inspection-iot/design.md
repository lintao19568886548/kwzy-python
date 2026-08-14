## Context

FacilityOps currently contains the rebuilt WorkOrder lifecycle only. The legacy evidence repository has separate `firefighting`, `transformer`, `elevator`, `hygiene_check` and `factory_maintenance` CRUD paths whose inspection fields are mostly unbounded strings, whose records can be physically deleted and whose public register endpoints can write the default tenant without authenticated identity. There is no legacy evidence for periodic plan generation, checklist snapshots, alarm correlation, escalation, a device-to-provider binding contract or reliable IoT-to-WorkOrder delivery.

This change crosses database, domain, API, security, WorkItem/outbox/audit, PC and migration boundaries. It must run on PostgreSQL 16, preserve the existing tenant/park authorization model and integrate with WorkOrders without exposing external provider claims that cannot be verified locally.

## Goals / Non-Goals

**Goals:**

- Unify supported facility types under a tenant/park-scoped device aggregate with controlled retirement and append-only history.
- Generate weekly inspection tasks deterministically from immutable published template versions and active schedules.
- Capture structured checklist evidence, create exceptions and atomically link failed critical checks to one governed WorkOrder.
- Provide a truthful local/sandbox IoT adapter boundary, persisted device bindings and replay-safe alarm ingestion/correlation/escalation.
- Enforce database-derived permissions, park scope, strict schemas, idempotency and optimistic concurrency through API, PG and browser evidence.
- Rehearse versioned legacy maintenance migration without copying unsafe URLs, raw PII, ambiguous mappings or fabricated IoT facts.

**Non-Goals:**

- Connecting a real vendor, storing provider secrets in the database, contacting production endpoints or claiming live IoT completion.
- Implementing inventory consumption, procurement/supplier settlement, metering-to-billing or access-control visitor journeys.
- Implementing the independent employee mobile app or tenant mini-program; responsive PC evidence is not counted as either.
- Preserving physical deletion or anonymous default-tenant registration from the legacy system.

## Decisions

### Device aggregate and immutable history

`FacilityDevice` owns tenant, park, optional unit, type, code, name, location, criticality, lifecycle state and lock version. Every material change appends a `FacilityDeviceHistory` snapshot. Device codes are tenant-unique; tenant/park/unit relationships use composite foreign keys. Retirement is a state transition and is denied while active tasks or open alarms exist. This replaces per-type tables because their shared identity, scheduling and alarm behavior is stronger than their legacy field differences; type-specific properties remain bounded JSON validated by the application.

### Published inspection definitions are immutable snapshots

Templates use logical code plus version number and DRAFT/PUBLISHED/RETIRED states; items have stable item codes, result type, bounds and critical flag. Schedules reference an exact published template version and device. Generated tasks snapshot the version and a local weekly window. A partial unique constraint on schedule/window plus a row lock makes repeated or concurrent generation create one task. Editing requires a new draft version rather than mutating evidence already used by tasks.

### Inspection tasks integrate through existing WorkItem and WorkOrder boundaries

Inspection tasks have PENDING/IN_PROGRESS/SUBMITTED/PASSED/FAILED/MISSED/CANCELLED states and expected-version transitions. Results are one row per snapshotted item with bounded typed values and safe evidence references. A critical failure appends an `InspectionException`, opens one remediation WorkOrder using a stable inspection source id, and emits WorkItem/outbox/audit changes in the same transaction. Non-critical failures remain explicit exceptions and can be promoted by an authorized manager. Calling the existing WorkOrder application boundary is preferred over duplicating its state machine.

### Provider truth and credentials remain outside business rows

`IoTProvider` stores adapter kind, status, credential reference and last health facts, never a secret. `IoTDeviceBinding` maps one tenant/park device to a provider/external key with lifecycle history. Local and sandbox adapters can be exercised; production startup or a CONNECTED transition requires a supported adapter and an environment-resolved credential reference. Missing real credentials means `NOT_CONNECTED`, not a fake success.

### Alarms separate immutable source events from correlated incidents

Every accepted payload becomes an immutable `IoTAlarmEvent` keyed by provider/source event id. Canonical `IoTAlarm` incidents correlate by binding and normalized type inside a bounded window; exact replay returns the same event, while a new correlated event increments occurrence count and severity monotonically. OPEN/ACKNOWLEDGED/RESOLVED/CLOSED transitions require expected version. Escalation levels have a unique `(alarm, level)` constraint, and HIGH/CRITICAL policy creates one linked WorkOrder using a stable alarm source id.

### Ingress is authenticated and fail closed

The delivered API uses database-derived `iot:ingest` permission for local/sandbox ingestion and validates provider status, binding, timestamp bounds, nonce/source id and strict body fields. A future public vendor webhook must be implemented by a provider adapter with signature verification and replay storage; no anonymous generic callback is exposed in this change. This is intentionally safer than the legacy public default-tenant register path.

### PC is one live operations workspace

A single Facility Operations PC view uses live APIs for device registry, inspection queue and alarm queue. Permission-gated drawers perform create/publish/schedule/start/submit/acknowledge/escalate/resolve operations. Status has text in addition to color; 1440/820/390 widths, empty/loading/403/409/offline/retry and drill-down links are tested. The page does not embed fixture JSON.

## Risks / Trade-offs

- [Bounded JSON can drift by device type] → validate against a server-owned type profile, cap keys/depth/size and persist normalized query fields outside JSON.
- [Weekly time windows are timezone-sensitive] → store timezone and local weekday/time on schedule, persist UTC window boundaries on tasks and test Asia/Shanghai DST-independent behavior.
- [Concurrent alarm events can create two open incidents] → lock the binding/open incident query and add a partial unique active-correlation constraint plus PG race tests.
- [Nested WorkOrder creation can partially commit] → share one SQLAlchemy transaction and expose an internal application method that never commits independently.
- [External vendors use incompatible signatures/severity] → keep adapter ports and canonical mappings explicit; unsupported/live states fail closed and remain tracked under the external-platform capability.
- [Legacy rows mix device master and inspection occurrence] → migration separates deterministic device identity from occurrences; ambiguous rows are quarantined rather than guessed.

## Migration Plan

1. Add forward-only revisions after `y1b79d4e6f53`; never edit applied history.
2. Upgrade an empty PostgreSQL 16 database, compare metadata, run `current == heads`, downgrade one revision and upgrade again.
3. Deploy new tables/routes with providers defaulting to `NOT_CONNECTED`; no external network call occurs.
4. Run synthetic dry/interruption/apply/reapply/reconcile/schema-rollback for the legacy maintenance shapes and alarm fixture.
5. For real migration, require authorized schema/dictionary, desensitized sample, park/unit/device key maps, attachment inventory and signed counts before applying.
6. Rollback application traffic first, then downgrade only the newest revision if no new facility data has been accepted; otherwise use forward repair and evidence-preserving export rather than destructive downgrade.

## Open Questions

- Real vendor protocol, credential source, callback allowlist and signature scheme are external evidence blockers.
- Real legacy device identity rules across repeated firefighting/transformer/elevator rows require a signed mapping from the data owner.
- Employee mobile scanning, offline queue and camera integration remain for the independent employee mobile capability.
