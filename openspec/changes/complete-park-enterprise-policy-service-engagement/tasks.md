## 1. Independent evidence and specification closure

- [x] 1.1 Inspect the product blueprint, current Python/PC code, the two latest legacy Java/PC copies, and supplied SQL for policy, service, activity, and announcement evidence.
- [x] 1.2 Publish the legacy disposition and field mapping, classifying external read-only notices, Party, WorkOrder, CRM activity, and notification records as sources or boundaries rather than completed engagement aggregates.
- [x] 1.3 Record local product truth plus explicit government feed, provider, payment, external notification, mini-program, real migration, and production blockers.

## 2. Domain and persistence

- [x] 2.1 Implement engagement domain entities and transition rules for policy, service case, park activity, announcement, immutable versions, audience, and append-only evidence.
- [x] 2.2 Implement tenant/park/Party composite relationships, uniqueness, checks, indexes, checksums, idempotency fingerprints, and optimistic lock fields.
- [x] 2.3 Add one forward Alembic revision after `d6a13e9f0b98` and verify fresh PostgreSQL 16 plus existing-head upgrade/downgrade/re-upgrade.
- [x] 2.4 Compare ORM metadata with migrated schema and test core database constraints, cross-boundary rejection, and append-only protections.

## 3. Policy governance

- [x] 3.1 Implement policy drafts, immutable versions, provenance, controlled links/attachments, checksums, effective windows, and normalized query.
- [x] 3.2 Implement native approval, exact-version publication, expiry, withdrawal, and auditable lifecycle events.
- [x] 3.3 Implement bounded applicability rules, permitted Party-profile projection, explainable match/unmet reasons, follows, and idempotent local consultations.
- [x] 3.4 Add policy lifecycle, matching, tenant/park/Party isolation, link safety, idempotency, and official-eligibility-boundary tests.

## 4. Enterprise-service catalogue and cases

- [x] 4.1 Implement service drafts/versions, eligibility, SLA, appointment/evidence rules, price truth, and internal versus unconnected provider states.
- [x] 4.2 Implement persisted Party-bound tenant intake, staff-on-behalf validation, idempotent case creation, and separate customer/staff projections.
- [x] 4.3 Implement append-only assignment, appointment, evidence, progress, result, dispute, cancellation, SLA escalation, confirmation, optional governed WorkOrder handoff, and feedback.
- [x] 4.4 Add service lifecycle, transition, SLA, provider-boundary, tenant/park/Party isolation, idempotency, and concurrent appointment tests.

## 5. Park activities

- [x] 5.1 Implement activity drafts, immutable approved versions, schedule/location/audience/registration rules, attachments, capacity, and cancellation terms.
- [x] 5.2 Implement Party-bound idempotent registration, database-serialized capacity, ordered waitlist, and non-overbooking constraints.
- [x] 5.3 Implement cancellation, single promotion, check-in evidence, completion/cancellation events, and attended-Party feedback.
- [x] 5.4 Add activity transition, isolation, idempotency, last-seat concurrency, waitlist promotion, check-in, and feedback tests.

## 6. Announcements and delivery

- [x] 6.1 Implement announcement drafts, sanitized immutable versions, priority/pin/schedule/expiry, native approval, exact publication, and withdrawal.
- [x] 6.2 Implement bounded audience rules and frozen recipient snapshots across users, roles, Parties, parks, and tenant principals.
- [x] 6.3 Publish registered outbox events and implement batched idempotent in-app notification fan-out, delivery ledger, read receipts, retry, and failure evidence.
- [x] 6.4 Add announcement lifecycle, audience isolation, partial-retry, recipient uniqueness, read/expiry/withdrawal, and false-external-delivery tests.

## 7. API, authorization, and security

- [x] 7.1 Mount strict staff and tenant-principal engagement routers and publish matching runtime/YAML OpenAPI paths, schemas, errors, idempotency, and expected-version contracts.
- [x] 7.2 Seed and enforce engagement permissions with database-derived tenant/park/Party scope, staff/tenant projections, and non-disclosing foreign-resource behavior.
- [x] 7.3 Add unknown-field, parameter-pollution, bulk atomicity, IDOR, injection, XSS, URL/SSRF, sensitive-field, audit, and forged-claim tests.
- [x] 7.4 Add real HTTP staff and tenant journeys covering policy consultation, service case, activity registration/check-in, and announcement publish/read.

## 8. PC engagement workspace

- [x] 8.1 Add permission-aware `/engagement` routing/navigation, typed API client, and real overview metrics with separate staff and tenant-principal modes.
- [x] 8.2 Add policy, services, activities, and announcements views with governed drawers/actions, truth labels, version/audience/capacity/SLA/read evidence, and deep links.
- [x] 8.3 Add desktop, 820px, and 390px loading, empty, permission, validation, conflict, expired, withdrawn, offline, retry, accessible-text, and no-body-overflow states.
- [x] 8.4 Add frontend unit/build gates and real browser E2E with screenshot evidence for staff and tenant-principal journeys.

## 9. Migration and operations

- [x] 9.1 Add a documented synthetic engagement fixture and importer with dry run, deterministic keys, checkpoint/resume, interruption rollback, replay, quarantine, and provenance.
- [x] 9.2 Add reconciliation for versions, active windows, cases, capacity, registrations, audiences, deliveries, reads, and quarantine plus run-scoped rollback.
- [x] 9.3 Add backup/delete/restore rehearsal and keep real standalone notice/policy/service/activity migration visibly blocked without authorized exports and key maps.
- [x] 9.4 Add engagement acceptance stages, worker/fan-out operations evidence, performance thresholds, and no-production-contact assertions to local staging.

## 10. Exact acceptance and closure

- [x] 10.1 Run backend unit, integration, security, isolation, idempotency, and concurrency suites.
- [x] 10.2 Run PostgreSQL 16, Alembic, ORM/schema, real HTTP, worker, performance, and backup/restore gates.
- [x] 10.3 Run PC lint, typecheck, unit, production build, and browser E2E at desktop/tablet/390px.
- [ ] 10.4 Run OpenAPI, OpenSpec strict, secret, dependency, architecture, stub/fake, and final-quality gates at one exact SHA.
- [ ] 10.5 Update capability matrix, findings, evidence index, migration truth, and status without overstating external providers, mini-program, production, or real legacy migration.
- [ ] 10.6 Commit and push normally, sync/archive specs only after exact-SHA acceptance, and do not merge main before every remaining global gate closes.
