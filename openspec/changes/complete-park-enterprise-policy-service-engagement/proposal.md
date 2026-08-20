## Why

The rebuilt product has governed Party profiles, tenant-service work orders, approvals, attachments, outbox delivery, and in-app notifications, but it has no mounted policy, park-enterprise service, activity, or announcement business module. The latest two legacy Java copies only expose a read-only `/notices/list` backed by a separately configured database and the supplied `magic.sql` contains no authoritative aggregate for these capabilities, so this slice must create governed local product truth without inventing a completed legacy migration.

## What Changes

- Add a versioned policy catalogue with source provenance, applicability rules, effective/expiry control, governed publication/withdrawal, explainable Party matching, and follow/consultation evidence.
- Add versioned park-enterprise service catalogues and provider truth, plus tenant-bound service requests, appointment/case lifecycle, SLA, evidence, result confirmation, and feedback distinct from facility repair WorkOrders.
- Add governed park activities with immutable published snapshots, registration windows, capacity, concurrency-safe waitlists, cancellation/promotion, check-in evidence, completion, and feedback.
- Add versioned announcements with native review/approval, scheduled publication, park/audience snapshots, pin/expiry/withdrawal, read acknowledgements, and idempotent outbox/in-app fan-out.
- Mount strict tenant/park/permission-scoped HTTP APIs and a responsive PC workspace with separate staff and tenant-principal projections.
- Add one additive PostgreSQL migration and a synthetic, repeatable, resumable migration/reconciliation/rollback harness.
- Keep government policy feeds, external service providers, ticket/payment platforms, SMS/WeChat/email delivery, tenant mini-program delivery, production credentials, and real legacy notice migration explicitly unavailable or blocked until governed contracts and authorized exports exist.

## Capabilities

### New Capabilities
- `park-policy-governance`: Versioned policy provenance, publication, applicability, explainable matching, expiry, withdrawal, and consultation evidence.
- `enterprise-service-catalog-case`: Governed service catalogues, provider truth, tenant-bound request/case lifecycle, SLA, evidence, confirmation, and feedback.
- `park-activity-registration`: Governed activity publication, capacity, registration/waitlist, check-in, completion, cancellation, and feedback.
- `park-announcement-publication`: Versioned announcement review, scheduling, audience snapshots, read acknowledgement, withdrawal, and notification fan-out.
- `park-enterprise-engagement-api`: Strict mounted APIs with database-derived tenant, park, Party, permission, validation, idempotency, and audit boundaries.
- `park-enterprise-engagement-pc`: Permission-aware staff and tenant-principal PC workspace with real data and responsive failure/retry states.
- `park-enterprise-engagement-data-migration`: Truthful synthetic migration rehearsal and an explicit blocker for the unavailable standalone legacy notice database and other source aggregates.

### Modified Capabilities

None. Existing Party, approval, attachment, event-outbox, notification-inbox, and tenant-service capabilities are reused without changing their published requirements.

## Impact

- API: new engagement domain/application/infrastructure/interface layers, router mounting, permission catalogue entries, OpenAPI paths, idempotent commands, and audit/outbox integration.
- Database: one forward Alembic revision for policy, service, activity, announcement, audience, registration, case, receipt, event, and migration provenance tables with tenant/park composite constraints.
- Web: new `/engagement` route, typed API client, staff/tenant projections, and desktop/tablet/390px operational journeys.
- Operations: PostgreSQL 16 migration checks, synthetic ETL, real HTTP, concurrency, security, browser, performance, backup/restore, and evidence gates; no production or external-provider contact.
