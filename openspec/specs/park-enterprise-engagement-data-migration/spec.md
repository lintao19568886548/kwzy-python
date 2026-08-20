# Park Enterprise Engagement Data Migration

## Purpose

Define truthful, repeatable, reconcilable, and reversible engagement data migration.

## Requirements

### Requirement: Truthful engagement migration provenance
The migration tooling SHALL distinguish synthetic fixture, authorized de-identified snapshot, and real source data for policies, services, activities, and announcements and SHALL persist source/run provenance on every imported record.

#### Scenario: Import bundled fixture
- **WHEN** the bundled engagement fixture is imported
- **THEN** the run and records are labelled synthetic and no report claims production or legacy replacement

### Requirement: Repeatable resumable import
The tooling SHALL support dry run, deterministic source keys, checkpoint/resume, interruption rollback, repeat execution, quarantine, and zero-duplication replay.

#### Scenario: Resume after interruption
- **WHEN** an import stops after a committed checkpoint
- **THEN** resume continues without duplicating prior content versions, cases, registrations, audience targets, or receipts

### Requirement: Reconciliation and rollback
The tooling SHALL reconcile source and target counts, versions, active windows, capacities, registrations, audience totals, reads, and quarantine reasons and SHALL support run-scoped rollback plus backup/delete/restore rehearsal.

#### Scenario: Audience reconciliation mismatch
- **WHEN** target announcement audience or receipt totals differ from the accepted source mapping
- **THEN** reconciliation fails visibly and the run cannot be reported as accepted

### Requirement: Real legacy and external-source closure gate
Real migration SHALL remain `BLOCKED` until the standalone notice database schema/export, source ownership, policy/service/activity sources, tenant/park/Party key maps, content/link policy, tolerances, and accountable sign-off are supplied.

#### Scenario: Only `magic.sql` and legacy code are available
- **WHEN** the supplied dump has no engagement aggregates and the external notice database export is absent
- **THEN** tooling may run synthetic rehearsal only and no status may claim real notice or engagement migration completion
