# Supply Data Migration

## ADDED Requirements

### Requirement: Truthful migration provenance
The migration tooling SHALL distinguish synthetic fixture, de-identified snapshot, and real source data and SHALL never label synthetic rows as production evidence.

#### Scenario: Run synthetic rehearsal
- **WHEN** the bundled fixture is imported
- **THEN** every run and report is labelled synthetic and real migration remains blocked

### Requirement: Repeatable resumable import
The tooling SHALL support dry run, deterministic source keys, checkpoint/resume, repeat execution, quarantine, and zero-duplication replay.

#### Scenario: Resume after interruption
- **WHEN** a run stops after a committed checkpoint
- **THEN** resume continues from that checkpoint without duplicating earlier suppliers, materials, orders, or movements

### Requirement: Reconciliation and rollback
The tooling SHALL reconcile counts and financial/quantity totals, report quarantined rows, produce compensating rollback scoped to one run, and support backup/delete/restore rehearsal.

#### Scenario: Reconcile stock totals
- **WHEN** an import completes
- **THEN** source movements, target movements, and target balance projections reconcile or the run fails visibly

### Requirement: Real-data closure gate
The system SHALL keep real migration `BLOCKED` until authoritative schema/export, field mapping, reconciliation tolerances, and accountable business sign-off are available.

#### Scenario: Missing authoritative export
- **WHEN** only inferred or synthetic source data exists
- **THEN** no report may claim legacy replacement or production migration completion
