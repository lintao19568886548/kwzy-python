## Context

The authoritative blueprint defines employee onboarding, location punch, leave, attendance aggregation and payroll preparation. The legacy Java implementation hard-codes office locations and separates attendance/payroll logic across modules; employee writes do not reliably synchronize identity, leave writes do not start approval or recomputation, and neither performance nor qualifications exist. The Python platform already provides identity users, tenant/park scope, native approval, WorkItems, attachments and chained audit logs.

## Goals / Non-Goals

**Goals:** deliver operational employee, roster, attendance, leave, performance and qualification governance with PostgreSQL, real HTTP and browser evidence; minimize location/identity data; reuse platform controls; publish repeatable migration evidence.

**Non-Goals:** raw biometric storage, continuous trajectory tracking, payroll calculation/payment, production device integration, or migration of real employee PII without explicit authorization and a desensitized source.

## Decisions

### Employee is linked to, not duplicated from, identity

`WorkforceEmployee` stores workforce number, display name, employment dates/status, park assignment and optional identity `user_id`. Phone/identity-card inputs are normalized into masked suffix/fingerprint facts; raw values are not returned or written to logs. One active employee may link to one user per tenant and park scope is always repository enforced.

### Shift definitions are immutable versions

`ShiftTemplate` owns a stable code while `ShiftTemplateVersion` snapshots start/end, cross-day and break minutes. `ShiftAssignment` points to an exact version and date. Database uniqueness and row locking prevent two active assignments for the same employee/date; inactive employment or approved full-day leave blocks assignment.

### Attendance stores minimum location evidence

Locations are configurable park assets with a deployment configuration reference, radius and label. A punch may include coordinates for transient distance validation, but persists only location id, distance/result, device fingerprint and time. Exact coordinates and continuous trajectories are never retained.

### Leave relies on native approval truth

Submission creates one native approval keyed by leave id and idempotency key. Domain status is reconciled from the authoritative approval request; approval creates roster conflicts and triggers summary regeneration.

### Performance and qualifications preserve evidence

A reviewer cannot review themself; publishing locks rating/comment evidence and employee acknowledgement is separate. Qualification types define validity/reminder policy; credentials reference same-scope attachments, retain masked/fingerprint facts and expire through an idempotent WorkItem sweep.

### Application does not depend on ORM

Pure domain validators accept primitives. Application services orchestrate repositories and platform services. Routers parse strict schemas and never issue database queries. Repositories alone import SQLAlchemy models.

## Risks / Trade-offs

- [Precise attendance location is privacy-sensitive] → calculate transiently and persist only derived distance/result; no trajectory table.
- [Approval and schedule may race] → lock employee/date and leave rows and use database uniqueness/expected versions.
- [Legacy fields are incomplete] → quarantine unknown tenant/park/user/status/date mappings; never invent identities, punches or qualifications.
- [Payroll expectations exceed this capability] → expose payroll-ready summaries but keep payroll calculation/payment blocked pending rules and authorization.
- [Real device integration is unavailable] → provide a typed adapter boundary and truthful `NOT_CONNECTED` status.

## Migration Plan

1. Add one forward-only revision after `b4ea2c7d8f86`; never edit applied revisions.
2. Upgrade empty PostgreSQL 16, assert current=heads, downgrade one and re-upgrade, and verify metadata/constraints/indexes.
3. Seed permissions and deploy API/UI without enabling a production attendance device.
4. Run synthetic dry-run, interruption, apply, reapply and reconcile; quarantine invalid park/user/time/PII rows.
5. Real cutover requires authorized schemas/dictionaries, desensitized extracts, counts and payroll ownership decisions.
6. After workforce evidence exists, use forward repair/export rather than erasing history.

## Open Questions

- Which biometric/access-control vendor and signed callback contract are authorized?
- What are production shift, leave, overtime, holiday and payroll rules?
- Which qualifications require regulatory verification?
- No authorized legacy HR snapshot or payroll reconciliation baseline has been supplied.
