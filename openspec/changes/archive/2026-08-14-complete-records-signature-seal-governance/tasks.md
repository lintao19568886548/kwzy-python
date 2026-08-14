## 1. Evidence and specification

- [x] 1.1 Reconcile blueprint, legacy Java/frontend/DDL and current attachment/lease-document evidence
- [x] 1.2 Record absence of legacy archive/signature/seal aggregates and current fake-SIGNED/legal-risk boundary
- [x] 1.3 Define records retention/access/disposition, seal custody/use and signature-provider truth contracts

## 2. Domain and persistence

- [x] 2.1 Add pure domain rules for record, retention, hold, custody, use, signature and separation of duties
- [x] 2.2 Add records, revision/integrity, access/disposition, seal and signature ORM models
- [x] 2.3 Add forward Alembic revisions after `z2c80e5f6a64` without editing applied history
- [x] 2.4 Add tenant/park composite FKs, checks, partial uniques, indexes and metadata parity tests

## 3. Records classification and integrity

- [x] 3.1 Add category create/list/update/retire with versioned retention policy
- [x] 3.2 Add deterministic concurrent-safe archive number allocation and record lifecycle
- [x] 3.3 Add same-scope attachment-backed immutable revisions with server-derived SHA-256
- [x] 3.4 Add filing, integrity verification, mismatch hold and safe record detail/timeline

## 4. Records access and disposition

- [x] 4.1 Add reasoned legal hold and release with append-only events
- [x] 4.2 Add access/borrow request, platform approval linkage, checkout/return/expiry
- [x] 4.3 Add disposition request with retention/dependency gates and platform approval linkage
- [x] 4.4 Add two-person confirmation, checksum manifest and metadata-only local disposition

## 5. Seal registry and use

- [x] 5.1 Add typed seal create/list/detail with park scope and normalized unique code
- [x] 5.2 Add transfer proposal/acceptance, loss/suspension/recovery/retirement and custody history
- [x] 5.3 Add exact record-revision seal-use application and native approval linkage
- [x] 5.4 Add custodian execution, high-risk separation of duties and immutable idempotent receipt

## 6. Electronic signatures and Lease integration

- [x] 6.1 Add secretless provider registry and truthful NOT_CONNECTED/SANDBOX/CONNECTED/DEGRADED health
- [x] 6.2 Add exact-revision envelope, participant and append-only provider event lifecycles
- [x] 6.3 Add authorized replay-safe sandbox ingest/dispatch and fail-closed live configuration
- [x] 6.4 Harden Lease sign so sandbox cannot append legal SIGNED and project envelope truth in detail

## 7. API and security

- [x] 7.1 Add explicit strict schemas and mounted records/seal/signature routes
- [x] 7.2 Add database-derived permissions, tenant/park/parent-child IDOR and forged-token tests
- [x] 7.3 Add unknown field, duplicate parameter, upload/content, idempotency, stale-version and race tests
- [x] 7.4 Align runtime and YAML OpenAPI exact methods and stable error schemas

## 8. PC governance workspace

- [x] 8.1 Add live records catalogue/detail, category, revision, filing, retention, hold and integrity views
- [x] 8.2 Add access/borrow/disposition queues with approval and evidence drill-down
- [x] 8.3 Add seal registry/custody/use and signature provider/envelope views with truthful labels
- [x] 8.4 Add role-aware loading/empty/403/409/offline/retry states at desktop/tablet/mobile widths

## 9. Migration readiness

- [x] 9.1 Publish legacy disposition, field map, retention decisions and quarantine codes
- [x] 9.2 Add versioned synthetic metadata/binary fixture without real PII or fabricated seal/signature claims
- [x] 9.3 Implement dry/apply/interruption/reapply/reconcile/rollback and real-input blockers

## 10. Verification

- [x] 10.1 Add domain/repository/API/PG concurrency and real HTTP regression coverage
- [x] 10.2 Add Playwright role, responsive, conflict/error and visual evidence
- [x] 10.3 Run focused PG16/backend/frontend/OpenAPI/OpenSpec/stub/secrets gates
- [x] 10.4 Run clean-SHA full acceptance including performance, backup/restore and all migrations

## 11. Closure

- [x] 11.1 Update matrix/register/roadmap/state and versioned evidence without claiming live provider or real migration
- [x] 11.2 Normally commit/push, sync specs and archive without force
