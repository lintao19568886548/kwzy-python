# workforce-performance Specification

## Purpose
TBD - created by archiving change complete-workforce-scheduling-attendance-performance. Update Purpose after archive.
## Requirements
### Requirement: Cycles and goals are scoped
The system SHALL manage tenant/park cycles and employee goals with bounded dates, weights and versions.

#### Scenario: Goal weight overflow
- **WHEN** total goal weight would exceed the allowed total
- **THEN** no goal is saved

### Requirement: Published review evidence is immutable
A reviewer SHALL NOT review themself; publish SHALL lock evidence and employee acknowledgement SHALL be a separate event.

#### Scenario: Self review
- **WHEN** a subject user tries to publish their own review
- **THEN** the system returns 403
