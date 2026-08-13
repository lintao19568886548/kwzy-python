## 1. Baseline and contracts

- [x] 1.1 Inventory current Lead model/service/API/UI/tests and Party/Lease/Unit transaction boundaries
- [x] 1.2 Reconcile old investment/CRM/radar evidence and archive the implemented basic lead specification
- [x] 1.3 Publish legacy endpoint disposition and CRM V2 field mapping without claiming external radar replacement
- [x] 1.4 Validate all proposal/design/delta specs with `openspec validate implement-investment-crm-v2 --strict`

## 2. PostgreSQL schema and migration

- [x] 2.1 Extend leads with normalized identity, source, richer stage, pool, SLA, merge and lock-version fields
- [x] 2.2 Add append-only lead activity persistence and indexes
- [x] 2.3 Add append-only assignment event and merge lineage persistence and indexes
- [x] 2.4 Add expiring lead-unit lock persistence, Lease relation and ACTIVE uniqueness
- [x] 2.5 Backfill FOLLOWING to CONTACTING and deterministically derive normalized/pool/version projections
- [x] 2.6 Add tenant/source external-ref uniqueness and tenant/park/owner/stage/time query indexes
- [x] 2.7 Keep all constraints compatible with SQLite tests and PostgreSQL production dialect
- [x] 2.8 Pass Alembic unique-head, fresh base-to-head and one-step down/up checks

## 3. Lead lifecycle and duplicate governance

- [x] 3.1 Add entities/mappers/repositories for enhanced Lead, activity, assignment, merge and lock facts
- [x] 3.2 Implement standard stage transitions, FOLLOWING input compatibility, terminal/reopen rules and reason validation
- [x] 3.3 Require expected-version for Lead writes and map stale/unique conflicts to stable 409 business codes
- [x] 3.4 Implement deterministic normalized-phone/name/source duplicate candidate query with minimal scoped data
- [x] 3.5 Block high-confidence duplicates unless a non-empty override reason is authorized and audited
- [x] 3.6 Implement same-tenant/same-park merge with source MERGED state, lineage and current-funnel exclusion
- [x] 3.7 Add transaction-bound sanitized audit records for all lifecycle and duplicate writes
- [x] 3.8 Add SQLite/API and PostgreSQL tests for transitions, dedup, merge, stale versions and isolation

## 4. Public pool, assignment and activity pipeline

- [x] 4.1 Implement owner/public/manage visibility on every list, detail and aggregate repository query
- [x] 4.2 Implement assign/reassign/release/recycle commands with append-only ownership events
- [x] 4.3 Implement row-locked public claim so concurrent claims have exactly one winner
- [x] 4.4 Implement idempotent overdue recycle and cancel/reopen the correct owner follow-up work item
- [x] 4.5 Implement append-only CALL/NOTE/VISIT/QUOTE/NEGOTIATION activities and timeline query
- [x] 4.6 Project last/next follow-up, overdue state and stage changes from activity commands
- [x] 4.7 Add `lead:claim`, `lead:manage` and `lead:lock` bootstrap permissions and server enforcement
- [x] 4.8 Add API/PostgreSQL tests for privacy masking, owner scope, assignment history, claim race and recycle idempotency

## 5. Unit matching, locking and atomic conversion

- [x] 5.1 Implement deterministic current VACANT unit matching with area/usage/price scores and reason breakdown
- [x] 5.2 Implement lazy lock expiry and row-locked lock acquisition with bounded expiry time
- [x] 5.3 Project Unit RESERVED on lock and restore VACANT only when no active lock or effective Lease blocks it
- [x] 5.4 Implement lock release/renew commands with owner/manage permissions, expected version and audit
- [x] 5.5 Make Party and Lease creation optionally commit-free while preserving existing callers by default
- [x] 5.6 Make Lead conversion create Party, optional Lease DRAFT, lock association, activity, audit and todo closure in one transaction
- [x] 5.7 Make Lease activation reject foreign active locks and consume same-contract locks under the Unit row lock
- [x] 5.8 Add failure-injection rollback and idempotent conversion tests
- [x] 5.9 Add PostgreSQL concurrency tests for lock races, expiry/reacquire and Lease activation serialization

## 6. Funnel query and APIs

- [x] 6.1 Implement a shared scoped filter builder for park, owner, pool, stage, source, keyword and UTC range
- [x] 6.2 Implement reconciled list/board/detail responses with masked public summaries and full authorized timelines
- [x] 6.3 Implement new/open/won/lost/public/overdue/stage counts, conversion rate and first-follow duration with zero-denominator handling
- [x] 6.4 Implement stable source and owner breakdowns without leaking foreign owner data
- [x] 6.5 Add duplicate, merge, assignment, claim/release/recycle and activity request/response schemas and APIs
- [x] 6.6 Add unit match, lock/release/renew and lock-aware conversion APIs
- [x] 6.7 Add CRM summary/board/detail APIs and deterministic pagination/order
- [x] 6.8 Add reconciliation, masking, merged-exclusion, empty and cross-scope API tests

## 7. PC investment CRM workspace

- [x] 7.1 Replace manual park/owner/lead IDs with authorized park and real user selectors plus row/detail actions
- [x] 7.2 Add KPI cards, shared filters, pipeline board/list switching and public-pool mode
- [x] 7.3 Add detail drawer for profile, stage, duplicate candidates, activity timeline and assignment history
- [x] 7.4 Add create/override/merge, assign/claim/release/recycle and follow-up flows with validation feedback
- [x] 7.5 Add explainable unit matches, active lock countdown/release/renew and lock-aware conversion flows
- [x] 7.6 Keep controls permission/ownership-consistent while relying on server enforcement
- [x] 7.7 Implement loading, empty, error, forbidden, stale/conflict and success states without losing form context
- [x] 7.8 Pass desktop/tablet responsive, visible-focus, semantic-label and keyboard checks

## 8. Migration and compatibility evidence

- [x] 8.1 Publish old investment/CRM/radar API disposition and field/enum/PII mapping
- [x] 8.2 Implement synthetic traditional/CRM/radar-like Lead/activity/assignment/merge fixture validation
- [x] 8.3 Implement loopback-only isolated PostgreSQL dry-run, first apply and idempotent re-apply drill
- [x] 8.4 Reconcile stage/pool/owner distributions, activity/assignment/merge counts, orphans, duplicate source refs and rejected PII
- [x] 8.5 Prove isolated rollback and add the CRM drill to full local acceptance
- [x] 8.6 Keep real schema/data, external source ingestion and production cutover behind explicit human approval

## 9. Contracts and acceptance

- [x] 9.1 Update OpenAPI YAML and runtime contract tests for all CRM V2 APIs and deprecated FOLLOWING mapping
- [x] 9.2 Add Playwright primary path for park selection, pipeline, create, follow, match, lock and convert
- [x] 9.3 Add Playwright public claim, manager assignment/merge, read-only, 409 recovery and tablet keyboard scenarios with no skips
- [x] 9.4 Pass backend full tests including PostgreSQL concurrency and transaction rollback
- [x] 9.5 Pass frontend lint/typecheck/unit/build and full browser E2E
- [x] 9.6 Pass migration, CRM ETL, backup restore, secrets, diff and OpenSpec strict gates
- [x] 9.7 Update the four controlling rebuild documents with exact commit/report evidence and truthful blockers
- [x] 9.8 Commit and push a clean non-force non-production checkpoint

## Non-goals

Production DB access/deployment, authorized real legacy migration, radar crawling/proxy pools, WeCom callbacks, automatic outreach, AI scoring, employee mobile, tenant mini-program, contract approval/signature and unrelated billing/IoT work remain outside this change and MUST NOT be represented as completed by its local acceptance.
