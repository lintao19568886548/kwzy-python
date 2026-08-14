# inspection-template-schedule Specification

## Purpose
TBD - created by archiving change complete-facility-device-inspection-iot. Update Purpose after archive.
## Requirements
### Requirement: Inspection templates are immutable published versions
Inspection templates SHALL use a tenant-local logical code, version number and DRAFT/PUBLISHED/RETIRED lifecycle. A published version SHALL be immutable; editing SHALL create a new draft version while existing tasks keep the original snapshot.

#### Scenario: Revise a published weekly template
- **WHEN** a manager changes a published fire inspection checklist
- **THEN** a higher draft version is created and existing tasks still reference the prior published version

### Requirement: Checklist items have typed validation
Every template version SHALL contain ordered stable item codes with BOOLEAN, NUMBER, TEXT or SELECT result type, required/critical flags and bounded validation rules. Publishing SHALL reject empty, duplicate or internally inconsistent items.

#### Scenario: Invalid numeric bounds
- **WHEN** a NUMBER item has a minimum greater than its maximum
- **THEN** publication fails and the draft remains editable

### Requirement: Schedules bind exact device, template and local cadence
An active inspection schedule SHALL reference one ACTIVE same-tenant/park device, one published template version, an eligible assignee, timezone, weekday, local due time and completion window. Weekly schedules SHALL calculate and persist deterministic UTC window boundaries.

#### Scenario: Weekly schedule in Asia Shanghai
- **WHEN** a schedule is configured for Monday 09:00 in Asia/Shanghai
- **THEN** generated tasks use the correct local week and persisted UTC start/due boundaries

### Requirement: Task generation is repeat-safe and concurrent-safe
Generation SHALL lock or uniquely constrain `(schedule, window start)` so repeated workers or concurrent requests create one inspection task and one field WorkItem. Disabled/retired schedules and devices SHALL create no new task.

#### Scenario: Two generators run for one week
- **WHEN** two workers generate the same active schedule window concurrently
- **THEN** exactly one inspection task and one open WorkItem exist
