## 1. Evidence and contracts

- [x] 1.1 Record old traditional Investment, CRM/Radar, external lead, visit and approval evidence with replace/retain/block disposition
- [x] 1.2 Define assignment selection, viewing lifecycle, intent approval snapshot and channel signature formulas with explicit bounds
- [x] 1.3 Update migration mapping and external-integration boundary without claiming live provider or real-data completion

## 2. Persistence and migration

- [x] 2.1 Add pure-domain rule, viewing, intent and channel value/state contracts without ORM dependency
- [x] 2.2 Add tenant-safe ORM tables, composite foreign keys, partial uniques, checks and indexes
- [x] 2.3 Add one forward Alembic revision after `r4a02c7d9e86` without editing history
- [x] 2.4 Verify PG16 fresh upgrade, unique current=heads, downgrade -1/up and ORM metadata parity

## 3. Automatic assignment

- [x] 3.1 Implement scoped rule/version/member repositories and draft/publish/new-draft/retire lifecycle
- [x] 3.2 Implement bounded eligible-member validation, preview and deterministic capacity-aware selection
- [x] 3.3 Apply serialized automatic assignment on configured creation/channel/recycle triggers with public-pool fallback
- [x] 3.4 Preserve manual assignment override, append-only evidence, work items, audit and idempotent/concurrent behavior

## 4. Viewing management

- [x] 4.1 Implement scoped viewing/unit repositories, time/unit validation and overlap constraints
- [x] 4.2 Implement schedule/confirm/reschedule/complete/cancel/no-show transitions with optimistic locking
- [x] 4.3 Project exactly-once VISIT activity, Lead stage/SLA/work-item updates and transition audit

## 5. Intent approval and lock gate

- [x] 5.1 Implement intent application/version/unit repositories and immutable bounded snapshots
- [x] 5.2 Submit idempotently to a published `LEAD_INTENT` Approval Definition with non-PII snapshot
- [x] 5.3 Derive authoritative intent status from Approval Request and expose versions/approval deep link
- [x] 5.4 Require an unexpired approved intent for lock acquisition/renewal and contract-bearing conversion
- [ ] 5.5 Add stale, foreign, revoked, rejected, returned and concurrent inventory/approval regression coverage

## 6. Signed channel intake

- [x] 6.1 Implement channel lifecycle using environment secret references and local/live verification states
- [x] 6.2 Implement raw-body HMAC, timestamp skew, constant-time compare, request bounds and uniform authentication failure
- [x] 6.3 Implement unique inbox receive, allow-list normalization, Lead/source linkage and optional automatic assignment
- [x] 6.4 Implement bounded quarantine, safe preview and permissioned idempotent replay without raw secret/PII logging

## 7. API and authorization

- [x] 7.1 Add strict schemas/routes for rules, viewings, intents and channel administration/replay
- [x] 7.2 Add public signed channel event route outside JWT while retaining fail-closed tenant/channel resolution
- [x] 7.3 Seed separate database-derived permissions and prove fabricated claim/header/body permissions do not authorize
- [x] 7.4 Update runtime and YAML OpenAPI with exact method sets, envelopes and strict contract tests

## 8. PC CRM workspace

- [x] 8.1 Add assignment rule list/editor/member capacity/preview/conflict surfaces using live APIs
- [x] 8.2 Add viewing schedule/status/unit/outcome controls and timeline reconciliation
- [x] 8.3 Add intent draft/version/submit/status/approval-link and approved lock states
- [x] 8.4 Add channel configuration/inbox/quarantine/replay with truthful local-versus-live labels
- [x] 8.5 Add desktop/tablet/mobile loading/empty/403/409/offline/retry and keyboard/no-overflow states

## 9. Migration and verification

- [x] 9.1 Extend synthetic CRM dry/apply/interruption/reapply/reconcile/rollback without raw PII or provider calls
- [x] 9.2 Add domain, service, API, layer, tenant/park/IDOR, parameter-pollution and secret-leak tests
- [x] 9.3 Add PG16 concurrent assignment/viewing/approval/lock/inbox idempotency tests
- [x] 9.4 Add real HTTP create→auto-assign→viewing→intent→approval→lock→convert and signed channel journeys
- [x] 9.5 Add Playwright role/desktop/tablet/mobile/offline/conflict journeys and visual evidence

## 10. Closure

- [x] 10.1 Run focused backend/frontend tests, Ruff error gate, typecheck/build, strict OpenSpec and targeted stub/layer scans
- [ ] 10.2 Run full PG16 acceptance, backup/restore, performance and clean-SHA browser evidence
- [ ] 10.3 Update reports/matrix/roadmap/state, normally commit/push, sync main specs and archive without force
