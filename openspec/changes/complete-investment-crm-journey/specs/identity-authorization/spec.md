## ADDED Requirements

### Requirement: Investment completion permission separation
The system SHALL seed and enforce separate database-derived permissions for assignment-rule read/write/run, viewing read/write, intent read/write/submit and channel read/write/replay, independently of generic Lead read/write.

#### Scenario: Lead editor fabricates channel replay permission
- **WHEN** a caller with Lead write but without `lead.channel.replay` declares that permission in a token, header or body
- **THEN** replay is denied and no inbox, Lead, assignment or success-audit state changes

#### Scenario: Intent submit without approval authority
- **WHEN** a Lead owner has intent submit permission but is not an approval task assignee
- **THEN** the owner can submit the intent but cannot decide its Approval Task
