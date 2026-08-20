## Context

The current branch already provides tenant/park authorization, Party enterprise profiles, native approval, attachments, transactional outbox, in-app notifications, WorkItems, and responsive PC patterns. It does not mount `tenant_ops`, and there is no Python policy, enterprise-service, park-activity, or announcement aggregate.

The two latest legacy Java copies have identical notice controller/repository and PC list artifacts: `/notices/list` reads a separately configured `NOTICES_DATABASE_URL`, returns an empty page when it is absent or fails, and opens external links. The supplied `magic.sql` has no notice, policy, enterprise-service, or park-activity table. Therefore the local product may preserve compatible source fields and migration tooling, but cannot claim an authoritative legacy import until the standalone database schema/export is authorized.

## Goals / Non-Goals

**Goals:**

- Create one governed engagement bounded context for policy, enterprise-service, activity, and announcement operations.
- Reuse existing Party, park scope, approval, attachment, audit, outbox, notification, and WorkItem capabilities without weakening their boundaries.
- Provide deterministic, explainable policy matching and concurrency-safe activity/service operations.
- Deliver strict staff and tenant-principal APIs plus a real-data PC workspace.
- Prove PostgreSQL 16 migration, isolation, security, concurrency, synthetic migration, HTTP, browser, and operational gates.

**Non-Goals:**

- Government policy crawling, OCR, AI recommendations, subsidy eligibility certification, or filing applications with government systems.
- Live external service-provider fulfillment, venue/ticket payment, SMS/WeChat/email delivery, or a tenant mini-program.
- Production deployment, production credentials, or real legacy migration without the standalone notice database export and reconciliation owner.
- Recasting maintenance WorkOrders, CRM activities, Party profiles, or notification rows as these new business aggregates.

## Decisions

### One engagement bounded context with four aggregate families

A new `engagement` module owns Policy, EnterpriseService, ParkActivity, and Announcement aggregate families. Shared tenant, park, Party, user, approval, attachment, WorkItem, outbox, and notification identifiers remain references to existing platform truth. This avoids four tiny cross-dependent modules while keeping facility WorkOrder and CRM activity semantics separate.

Alternative considered: extend `tenant_ops` and reuse WorkOrder for every request. Rejected because the current `tenant_ops` is an unmounted tenant summary stub and repair/maintenance dispatch, quotation, cost, and acceptance rules do not model consultation, appointment, event registration, or content publication.

### Immutable versions and approval-gated publication

Policy, service catalogue, activity, and announcement records have editable drafts and immutable published versions. Submission creates a native approval instance with a checksum and audience/content snapshot. Only an approved exact version may publish; later edits require a new draft/version. Withdrawal and cancellation append events rather than altering published evidence.

Alternative considered: mutable rows with `published=true`. Rejected because readers, registrations, and notifications must retain the exact terms and audience they observed.

### Explicit audience and deterministic policy matching

Audience and applicability rules use a bounded typed rule model for park, region, Party role, industry, enterprise scale, tags, and effective dates. Matching reads permitted Party profile projections, records matched and unmet reasons, and never treats a suggestion as government eligibility or approval. Publication stores an audience snapshot; later profile changes do not rewrite historical delivery evidence.

Alternative considered: free-form expressions or AI matching. Rejected because they are hard to audit, unsafe to evaluate, and would overstate the absent AI/external-data capability.

### Enterprise-service cases are local coordination truth

A versioned service catalogue declares an internal team or explicitly unconnected external provider. Tenant principals are bound to an active Party and parks through persisted grants. Requests create append-only case events, SLA deadlines, appointments, evidence, result confirmation, and one feedback record. External-provider states remain `NOT_CONNECTED` unless a separately governed adapter returns verifiable evidence.

### Registration and waitlist are database serialized

Activity registration stores the exact published version, Party, attendee count, and idempotency fingerprint. PostgreSQL row locks and unique constraints protect capacity. Full activities create ordered waitlist entries; cancellations promote the next eligible entry exactly once. Check-in and feedback are separate append-only evidence, not mutable attendance flags.

### Announcements fan out through existing outbox and inbox

Publishing appends a registered business event in the same transaction. An idempotent consumer resolves the frozen audience and creates at most one in-app notification per recipient. The announcement delivery ledger distinguishes targeted, delivered in-app, read, skipped, and failed states. No external channel is reported successful without a verified provider result.

### Strict authorization, links, and command safety

Permissions and tenant/park/Party scope are derived from database state on every request. Foreign identifiers return 404. Unknown fields, duplicate query parameters, unbounded lists, invalid transitions, and unsafe URL schemes/hosts fail closed. Mutations bind an idempotency key to a canonical request fingerprint and use optimistic versions or row locks. Logs and audit retain correlation and actor evidence without raw contact data or unrestricted content bodies.

Unlike the legacy synchronous notice-link probe, request paths do not fetch caller-controlled URLs. External source links are normalized and policy-validated; any future reachability check must be asynchronous, DNS-rebinding-safe, and separately evidenced.

### One role-aware PC workspace

`/engagement` provides policy, services, activities, and announcements. Staff actions and tenant-principal actions call separate route groups and projections. Desktop, 820px, and 390px layouts include loading, empty, permission, validation, conflict, offline, retry, and expired/withdrawn states. The PC is local product scope only and is not represented as a tenant mini-program.

### Truthful migration provenance

One additive Alembic revision follows `d6a13e9f0b98`. A synthetic legacy fixture models compatible notice rows plus policy/service/activity examples solely to exercise dry run, checkpoint/resume, replay, quarantine, reconciliation, rollback, and backup/restore. Real notice migration remains blocked until the standalone database schema/export, source ownership, link/content policy, Party/park key maps, and reconciliation tolerances are approved.

## Risks / Trade-offs

- [Audience fan-out can be large] → publish through outbox batches, bounded recipient snapshots, idempotent delivery, retry/dead-letter evidence, and performance gates.
- [Policy matching can be mistaken for official eligibility] → expose reasons and source dates, label it as local relevance guidance, and require external filing/decision status to remain unavailable.
- [Concurrent registrations can exceed capacity] → lock the activity capacity row, enforce unique Party/version registration, and promote waitlists transactionally.
- [Rich content or external links can create XSS/SSRF risk] → store sanitized bounded content/attachment references, restrict schemes/hosts, and never synchronously fetch arbitrary URLs.
- [Service cases can duplicate repair WorkOrders] → keep service-type taxonomy and case lifecycle distinct; link an optional WorkOrder only when a governed handoff is actually created.
- [Synthetic migration may be misreported as production] → persist provenance, keep real migration `BLOCKED`, and require evidence wording to state the boundary.

## Migration Plan

1. Add the engagement ORM and one forward PostgreSQL migration with composite tenant/park relationships, unique/check constraints, and indexes.
2. Upgrade a fresh PostgreSQL 16 database and an existing `d6a13e9f0b98` database to the new unique head; verify downgrade/re-upgrade without editing historical revisions.
3. Seed permissions and controlled local catalogue examples only in explicit local/test bootstrap paths.
4. Mount APIs and PC navigation behind permissions, then run API/PG/HTTP/browser/security/concurrency/performance gates.
5. Run synthetic migration and backup/delete/restore rehearsal; do not execute production migration or external calls.
6. Roll back application deployment before database downgrade if required; the migration downgrade removes only new engagement objects and is not a substitute for compensating business actions after real publication.

## Open Questions

No unresolved decision blocks local implementation. External policy-feed contracts, service-provider adapters, standalone notice export, production notification channels, and tenant mini-program delivery remain explicit future authorization gates rather than assumptions for this change.
