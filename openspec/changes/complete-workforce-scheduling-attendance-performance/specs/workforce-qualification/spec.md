## ADDED Requirements

### Requirement: Qualifications require scoped evidence
The system SHALL manage typed qualifications backed by same-scope attachments and masked credential facts.

#### Scenario: Cross-scope attachment
- **WHEN** a credential references another scope's attachment
- **THEN** it returns 404 and creates nothing

### Requirement: Expiry and revocation are actionable
An idempotent sweep SHALL expire due verified credentials and create one WorkItem; revocation SHALL require reason and preserve history.

#### Scenario: Repeated sweep
- **WHEN** expiry sweep repeats
- **THEN** only one open source WorkItem exists
