## ADDED Requirements

### Requirement: Rule-driven automatic assignment
The system SHALL support automatic assignment after configured Lead triggers using only a published same-tenant park rule version, current member eligibility and server-derived workload.

#### Scenario: Automatic assignment after channel intake
- **WHEN** an accepted channel Lead matches a published CHANNEL_INTAKE rule with an eligible member
- **THEN** the Lead becomes PRIVATE for that member and one `AUTO_ASSIGN` event records rule, version, trigger and explanation

### Requirement: Automatic assignment remains overridable
Users with Lead management permission SHALL retain explicit assign, reassign and release commands after automatic assignment, and these commands SHALL not rewrite the original automatic decision evidence.

#### Scenario: Manager reassigns automatic Lead
- **WHEN** a manager reassigns an automatically owned Lead using the expected Lead version and a reason
- **THEN** the owner changes, a REASSIGN event is appended and the original AUTO_ASSIGN event remains unchanged
