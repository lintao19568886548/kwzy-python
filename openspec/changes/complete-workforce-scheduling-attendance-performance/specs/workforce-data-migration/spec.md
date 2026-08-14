## ADDED Requirements

### Requirement: Legacy migration is repeatable and truthful
The tool SHALL support dry-run, apply, interruption, resume/reapply and reconciliation for employee, attendance and leave without fabricating users, punches, reviews or qualifications.

#### Scenario: Interrupted apply
- **WHEN** apply resumes after a committed batch
- **THEN** prior rows are not duplicated and remaining rows continue

### Requirement: Invalid or sensitive rows are quarantined
Unknown scope/user, invalid time/status, identity conflicts and unsupported trajectories SHALL receive stable redacted quarantine reasons.

#### Scenario: Raw trajectory source
- **WHEN** legacy input contains exact continuous coordinates
- **THEN** coordinates are discarded and no trajectory table is written

### Requirement: Real cutover requires evidence
The system SHALL NOT report real migration complete without authorized schemas, desensitized extracts, counts and reconciliation totals.

#### Scenario: Synthetic rehearsal completes
- **WHEN** synthetic checks pass without authorized real input
- **THEN** rehearsal passes while production migration stays BLOCKED_EXTERNAL_EVIDENCE
