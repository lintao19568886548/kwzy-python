## ADDED Requirements

### Requirement: Scoped viewing appointment lifecycle
The system SHALL manage tenant- and park-scoped Lead viewing appointments through `SCHEDULED`, `CONFIRMED`, `COMPLETED`, `CANCELLED` and `NO_SHOW` with optimistic locking and append-only transition evidence.

#### Scenario: Confirm scheduled viewing
- **WHEN** the Lead owner confirms a future scheduled viewing with the expected version
- **THEN** the appointment becomes CONFIRMED and the prior scheduling facts remain auditable

#### Scenario: Complete cancelled viewing
- **WHEN** a caller attempts to complete a cancelled viewing
- **THEN** the command fails without adding a VISIT activity or changing Lead stage

### Requirement: Current unit and time validation
A viewing SHALL reference one to twenty current same-park rentable units and a bounded start/end window, and the system SHALL reject overlapping active appointments for the same owner.

#### Scenario: Foreign unit supplied
- **WHEN** a viewing payload includes a Unit from another tenant or park
- **THEN** the request exposes no foreign metadata and persists no appointment rows

#### Scenario: Owner time conflict
- **WHEN** an owner already has an overlapping SCHEDULED or CONFIRMED viewing
- **THEN** the new appointment returns a stable conflict and neither appointment is modified

### Requirement: Viewing completion projects activity
Completing a viewing SHALL append exactly one VISIT activity containing bounded outcome facts, update follow-up projections and advance CONTACTING to VISITING without overwriting earlier activities.

#### Scenario: Idempotent completion retry
- **WHEN** the same completion command is retried with the same idempotency key
- **THEN** the existing completed appointment and one VISIT activity are returned with no duplicate timeline event
