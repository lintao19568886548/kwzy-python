## ADDED Requirements

### Requirement: Workbench automation permission separation
The system SHALL seed and enforce distinct permissions for personal layout configuration, role layout administration, notification access, automation rule read/write, scheduler read/run/write and event dead-letter replay.

#### Scenario: Layout editor lacks scheduler permission
- **WHEN** a caller can configure their workbench but cannot operate schedules
- **THEN** layout commands succeed while scheduler definitions and runs remain forbidden

#### Scenario: Client claim bypass attempt
- **WHEN** a valid token contains an automation permission absent from current database grants
- **THEN** protected automation operations remain forbidden
