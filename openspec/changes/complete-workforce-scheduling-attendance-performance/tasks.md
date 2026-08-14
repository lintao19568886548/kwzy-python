## 1. Evidence and specification
- [x] 1.1 Reconcile blueprint, legacy Java/frontend/DDL and current Python evidence
- [x] 1.2 Record legacy weaknesses, privacy boundary, payroll/device exclusions and real-data blockers
- [x] 1.3 Define employee, roster, attendance, leave, performance and qualification contracts

## 2. Domain and persistence
- [x] 2.1 Add pure workforce domain validators and state machines
- [x] 2.2 Add workforce ORM models without application-to-ORM dependency
- [x] 2.3 Add forward Alembic revision after `b4ea2c7d8f86`
- [x] 2.4 Add tenant/park keys, checks, partial uniques, indexes and metadata tests

## 3. Employee and roster
- [x] 3.1 Add PII-safe employee lifecycle and history
- [x] 3.2 Add explicit identity user binding/unbinding and active uniqueness
- [x] 3.3 Add shift template/version lifecycle
- [x] 3.4 Add assignment conflict, employment-date, leave and concurrency controls

## 4. Attendance and leave
- [x] 4.1 Add configurable policies and locations without persistent exact coordinates
- [x] 4.2 Add idempotent IN/OUT punches with derived evidence
- [x] 4.3 Add daily summary, anomaly review and reasoned adjustment
- [x] 4.4 Add leave submission/cancellation and native approval reconciliation

## 5. Performance and qualifications
- [x] 5.1 Add cycle and goal lifecycle
- [x] 5.2 Add no-self-review, publish locking and acknowledgement
- [x] 5.3 Add qualification types and evidence-backed credentials
- [x] 5.4 Add verification, revocation, expiry and WorkItems

## 6. API and security
- [x] 6.1 Add strict schemas and mounted routes
- [x] 6.2 Add database-derived permissions and scope/IDOR tests
- [x] 6.3 Add validation, PII-log, idempotency, stale-version and race tests
- [x] 6.4 Align runtime and YAML OpenAPI

## 7. PC workforce workspace
- [x] 7.1 Add employee and roster live views
- [x] 7.2 Add attendance, anomaly and leave operations
- [x] 7.3 Add performance and qualification evidence views
- [x] 7.4 Add role/failure/responsive states

## 8. Migration readiness
- [x] 8.1 Publish legacy disposition, field map, privacy and quarantine rules
- [x] 8.2 Add synthetic fixture without real PII/fabricated evidence
- [x] 8.3 Implement dry/apply/interruption/reapply/reconcile/rollback

## 9. Verification
- [x] 9.1 Add domain/repository/API/PG concurrency and real HTTP coverage
- [x] 9.2 Add Playwright role/responsive/error/visual evidence
- [x] 9.3 Run focused PG16/backend/frontend/contracts/security gates
- [ ] 9.4 Run clean-SHA acceptance including performance and backup/restore

## 10. Closure
- [ ] 10.1 Update matrix/register/roadmap/state and evidence truthfully
- [ ] 10.2 Commit/push, sync specs and archive without force
