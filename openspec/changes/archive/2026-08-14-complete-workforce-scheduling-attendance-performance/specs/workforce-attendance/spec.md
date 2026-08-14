## ADDED Requirements

### Requirement: Attendance configuration is park scoped
The system SHALL configure policy and location references per tenant/park rather than compile fixed office coordinates.

#### Scenario: Unknown location
- **WHEN** a punch references an inactive or other-park location
- **THEN** it is rejected without a punch

### Requirement: Punches are privacy-minimizing and idempotent
The system SHALL record punch type/time, location id, derived distance/result and device fingerprint but SHALL NOT persist exact request coordinates or trajectory. Same-key same-payload replay returns the original and changed payload conflicts.

#### Scenario: Replayed punch
- **WHEN** an equal command is retried with one key
- **THEN** exactly one punch exists

### Requirement: Summary adjustment preserves evidence
Daily summaries SHALL derive from roster, leave and punches; manual adjustment SHALL retain reason, prior values, actor and audit evidence.

#### Scenario: Missing checkout
- **WHEN** IN exists without qualifying OUT
- **THEN** the summary is anomalous rather than silently complete
