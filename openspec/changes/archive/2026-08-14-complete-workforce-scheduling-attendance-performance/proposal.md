## Why

The Python rebuild has organization, identity, approval, workbench and audit foundations, but it has no mounted workforce module. The legacy Java implementation offers employee CRUD, fixed-office attendance, leave CRUD and summary endpoints, yet it does not synchronize identity lifecycle, protect precise location data, govern schedule conflicts, drive leave approval, cover performance or qualifications, or provide reliable migration/cutover evidence. Treating those legacy endpoints as replacement would leave material operating and privacy gaps.

## What Changes

- Add tenant/park-scoped employee lifecycle records linked explicitly to identity users, with masked PII projections, fingerprints, status history and optimistic concurrency.
- Add versioned shift templates and dated assignments with overlap, leave and inactive-employee conflict protection.
- Add configurable attendance policies/locations, privacy-minimizing punches, daily summaries, anomaly review and adjustment evidence.
- Add leave requests linked to the native approval platform and automatic schedule/attendance recalculation gates.
- Add performance cycles, goals, manager reviews, employee acknowledgement and separation-of-duty rules.
- Add qualification types, employee credentials, evidence-backed verification, expiry/revocation and automatic WorkItems.
- Add strict mounted APIs, database-derived permissions, tenant/park isolation, idempotency and exact OpenAPI.
- Add a responsive PC workforce workspace with live HTTP data and actionable loading, empty, forbidden, conflict, offline and retry states.
- Add a synthetic, repeat-safe legacy HR migration rehearsal, quarantine/reconciliation rules and truthful blockers for unavailable real data.
- Preserve payroll-ready attendance summaries, but do not claim payroll calculation/payment replacement without authoritative salary rules and finance authorization.

## Capabilities

### New Capabilities

- `workforce-employee-lifecycle`: Employee identity linkage, scoped lifecycle, PII-safe projection and history.
- `workforce-shift-roster`: Versioned shifts, dated roster assignments and conflict control.
- `workforce-attendance`: Configurable policy/location, privacy-minimizing punches, summaries and anomaly adjustment.
- `workforce-leave-approval`: Leave submission, native approval linkage and roster/attendance consequences.
- `workforce-performance`: Cycles, goals, manager review, acknowledgement and immutable published evidence.
- `workforce-qualification`: Qualification catalogue, verified credentials, expiry/revocation and reminders.
- `workforce-api`: Strict scoped API, permissions, idempotency, concurrency and OpenAPI truth.
- `workforce-pc`: Responsive live workforce operations workspace.
- `workforce-data-migration`: Versioned legacy mapping, quarantine, repeatable rehearsal and reconciliation.

## Impact

- Backend: new workforce domain, SQLAlchemy models, repository/application boundaries, mounted FastAPI routes and approval/WorkItem/audit integration.
- Database: one forward-only Alembic revision after `b4ea2c7d8f86`, with PostgreSQL checks, composite scope keys, partial uniqueness and indexes.
- PC: a new `/workforce` route and permission-aware navigation using real APIs.
- Migration: synthetic legacy employee/attendance/leave fixtures only; no production or raw PII source is contacted.
- External boundaries: biometric devices, payroll engines and real legacy production data remain truthfully not connected until credentials, contracts and authorized datasets exist.
