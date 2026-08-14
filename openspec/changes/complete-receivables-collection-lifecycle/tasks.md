## 1. Evidence and specification

- [x] 1.1 Reconcile product request, docs, legacy Java/old UI/schema evidence and current implementation gaps
- [x] 1.2 Define schedule lineage, receipt/payment separation, explainable matching, aging and approval formulas
- [x] 1.3 Record external provider and real legacy data blockers without claiming live completion

## 2. Domain and persistence

- [x] 2.1 Add pure-domain billing, matching, unapplied balance, aging and adjustment rules
- [x] 2.2 Add tenant-safe models, checks, indexes, partial uniques and composite foreign keys
- [x] 2.3 Add forward Alembic revisions after `t6c24e9f1a08` without editing applied history
- [x] 2.4 Add schema/ORM parity and constraint tests

## 3. Schedule billing

- [x] 3.1 Add preview/apply query for eligible current-version Lease schedules
- [x] 3.2 Generate grouped issued Bills with source lineage and same-transaction schedule updates
- [x] 3.3 Enforce replay/concurrency safety and report version/overlap conflicts
- [x] 3.4 Wire audit, work items and outbox events

## 4. Receipt inbox and matching

- [x] 4.1 Implement single/batch finance receipt ingestion with source idempotency and channel capability gate
- [x] 4.2 Implement paginated pending/exception/dispute inbox with tenant/park scope
- [x] 4.3 Persist deterministic ranked candidates with rule codes and proposed allocations
- [x] 4.4 Implement finance confirm/exception and manager dispute resolution with row locks and audit

## 5. Payment allocation

- [x] 5.1 Expose exact allocated/unapplied balances on Payment reads
- [x] 5.2 Add later one-or-many Bill allocation with Idempotency-Key and ordered locks
- [x] 5.3 Preserve append-only allocation/reversal history and automatic settlement closure
- [x] 5.4 Add duplicate, over-allocation, cross-party/park/tenant and concurrent conflict tests

## 6. Collection and treatment

- [x] 6.1 Add L1-L4 aging rules, one active case per Bill and append-only collection records
- [x] 6.2 Add preview/apply dunning runs with repeat-safe escalation, work items and hold suppression
- [x] 6.3 Add adjustment request/approval/apply for waiver, extension, bad debt and dispute
- [x] 6.4 Close/suppress/reopen cases and work items from authoritative Bill state

## 7. API and security

- [x] 7.1 Add strict mounted schemas/routes and database-derived permissions
- [x] 7.2 Add IDOR, park scope, field permission, parameter-pollution and sensitive masking tests
- [x] 7.3 Align runtime and YAML OpenAPI exact method sets and error contracts
- [x] 7.4 Prove disconnected external providers cannot be reported as connected or successful

## 8. PC finance workspace

- [x] 8.1 Add live schedule-billing preview/apply and issued Bill lineage UI
- [x] 8.2 Add receipt inbox, match explanations, finance review and dispute drawer
- [x] 8.3 Add multi-bill/unapplied allocation and reversal states
- [x] 8.4 Add aging board, case history, adjustment approval status and provider truth
- [x] 8.5 Add loading/empty/403/409/offline/retry/no-overflow desktop/tablet/mobile states

## 9. Migration and verification

- [x] 9.1 Add versioned synthetic legacy finance fixture, mapping and quarantine rules
- [x] 9.2 Implement dry/apply/interruption/reapply/reconcile/rollback without raw PII
- [x] 9.3 Add domain/repository/API/PG concurrency/real HTTP regression coverage
- [x] 9.4 Add Playwright role, responsive, error and visual evidence
- [x] 9.5 Run focused and full PG16/backend/frontend/OpenAPI/OpenSpec/stub/secrets/performance/backup gates

## 10. Closure

- [ ] 10.1 Run clean-SHA acceptance and update matrix/roadmap/state/evidence
- [ ] 10.2 Normally commit/push, sync specs and archive without force
