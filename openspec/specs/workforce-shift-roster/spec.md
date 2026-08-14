# workforce-shift-roster Specification

## Purpose
TBD - created by archiving change complete-workforce-scheduling-attendance-performance. Update Purpose after archive.
## Requirements
### Requirement: Shift policy is versioned
The system SHALL keep stable shift templates and immutable published versions so historical assignments remain reproducible.

#### Scenario: Published shift edit
- **WHEN** a manager changes a published shift rule
- **THEN** a new version is created and old assignments retain their version

### Requirement: One effective assignment per employee date
The system SHALL reject duplicate, inactive-employment and approved full-day-leave assignment conflicts under concurrent writes.

#### Scenario: Concurrent assignment
- **WHEN** two workers assign the same employee/date concurrently
- **THEN** exactly one commits and the other conflicts
