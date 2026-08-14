## 1. Evidence and boundaries

- [x] 1.1 Record legacy rental-tenant and Radar enterprise-profile disposition, field mapping and replacement boundaries
- [x] 1.2 Record personal-identity, external-registry and real-data blockers without weakening accepted ADRs
- [x] 1.3 Define completeness, relationship canonicalization, risk summary and credential fingerprint formulas

## 2. Domain and persistence

- [x] 2.1 Add pure-domain enterprise profile, relationship, credential, tag and risk rules without ORM dependencies
- [x] 2.2 Add tenant-safe ORM models, composite foreign keys, checks, indexes and partial unique constraints
- [x] 2.3 Add exactly one forward Alembic revision after `s5b13d8e0f97` without editing history
- [x] 2.4 Add migration/model tests for boolean/check/index/FK/unique and ORM metadata parity

## 3. Enterprise profile

- [x] 3.1 Implement organization-only profile create/get/update with strict normalization and optimistic locking
- [x] 3.2 Implement exact completeness score and missing-dimension derivation from live child records
- [x] 3.3 Implement paginated enterprise directory filters and sort allow-list without hidden-field leakage
- [x] 3.4 Keep external provider state fail-closed as `NOT_CONNECTED`

## 4. Related companies

- [x] 4.1 Implement tenant/park-safe relationship repositories and endpoint visibility
- [x] 4.2 Implement directional and symmetric canonical edges, ownership bounds and active uniqueness
- [x] 4.3 Implement PostgreSQL tenant advisory locking and recursive `PARENT_OF` cycle rejection
- [x] 4.4 Implement optimistic end/history flow without physical delete

## 5. Credentials and attachments

- [x] 5.1 Implement organization-only credential metadata and same-tenant/scope attachment validation
- [x] 5.2 Reduce raw organization identifiers to fingerprint/masked suffix and prove no raw response/log/audit persistence
- [x] 5.3 Implement expiry/effective status and optimistic lifecycle
- [x] 5.4 Implement local review/reject transitions while forbidding fabricated external verification
- [x] 5.5 Enforce dedicated credential read/manage permissions

## 6. Tags and enterprise risk

- [x] 6.1 Implement tag provenance, confidence, active uniqueness, deactivation and concurrency handling
- [x] 6.2 Implement append-only risk signals with idempotent source references and attachment validation
- [x] 6.3 Implement append-only risk resolution with concurrent single-winner behavior
- [x] 6.4 Implement deterministic unresolved risk summary independent of blacklist state
- [x] 6.5 Enforce risk read/manage permissions and hidden-filter protection

## 7. API, audit and events

- [x] 7.1 Add strict schemas and mounted routes for all enterprise subresources and directory queries
- [x] 7.2 Enforce child-under-path ownership, tenant/park IDOR and parameter-pollution rejection
- [x] 7.3 Commit safe audit and business events in the same transaction for successful mutations
- [x] 7.4 Seed database-derived permissions and update runtime/YAML OpenAPI exact method contracts

## 8. PC enterprise workspace

- [x] 8.1 Replace the basic Party page with a live directory, filters, totals and responsive table/cards
- [x] 8.2 Add detail drawer overview/completeness/contact/address/park/profile sections
- [x] 8.3 Add related-company, credential, tag and risk panels with permissioned real mutations
- [x] 8.4 Add loading/empty/403/404/409/offline/retry/focus/no-overflow states at desktop/tablet/mobile widths
- [x] 8.5 Show external provider `NOT_CONNECTED` truthfully and remove any fake refresh behavior

## 9. Migration and verification

- [x] 9.1 Add versioned synthetic legacy enterprise fixture and safe quarantine cases
- [x] 9.2 Implement dry/apply/interruption/reapply/reconcile/rollback with no raw PII
- [x] 9.3 Add domain/service/API/layer/tenant/park/field-permission/security regression tests
- [x] 9.4 Add PostgreSQL concurrent relationship/tag/risk/profile regression tests
- [x] 9.5 Add real HTTP Party→profile→relationship→credential→tag→risk journey and negative cases
- [x] 9.6 Add Playwright desktop/tablet/mobile/offline/conflict journeys and visual evidence

## 10. Closure

- [x] 10.1 Run focused tests, Ruff error gate, typecheck/lint/build, strict OpenAPI/OpenSpec and stub/layer/secrets scans
- [x] 10.2 Run full PG16 fresh/down-up, ETL, performance, backup/restore and full browser acceptance
- [x] 10.3 Run clean-SHA acceptance, update matrix/roadmap/state, normally commit/push, sync main specs and archive without force
