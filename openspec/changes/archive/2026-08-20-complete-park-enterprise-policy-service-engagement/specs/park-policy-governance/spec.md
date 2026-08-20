## ADDED Requirements

### Requirement: Versioned policy provenance
The system SHALL retain immutable policy versions with source publisher, source identifier, source type, region, category, source publication time, effective/expiry dates, sanitized content or controlled attachments, validated source link, and checksum.

#### Scenario: Inspect a published policy
- **WHEN** an authorized user opens a published policy
- **THEN** the response identifies the exact version, source, effective window, checksum, and evidence without fetching or exposing an unsafe link

### Requirement: Governed policy publication lifecycle
The system SHALL permit draft editing, submit an immutable snapshot to native approval, publish only the approved exact version, and append expiry or withdrawal evidence without rewriting published content.

#### Scenario: Edit after approval
- **WHEN** an editor changes an approved policy draft before publication
- **THEN** the prior approval cannot publish the changed content and a new version requires review

#### Scenario: Withdraw an active policy
- **WHEN** an authorized publisher withdraws a policy with a reason
- **THEN** the policy becomes unavailable for new recommendations while its version and withdrawal event remain auditable

### Requirement: Explainable policy applicability
The system SHALL evaluate bounded park, region, Party role, industry, enterprise-scale, tag, and date rules against permitted Party profile fields and SHALL return matched and unmet reasons without claiming official eligibility.

#### Scenario: Party does not meet a rule
- **WHEN** a tenant principal views policy relevance and its Party profile misses a required criterion
- **THEN** the policy is labelled unmatched with a stable reason and no government eligibility decision is fabricated

### Requirement: Party-bound follow and consultation evidence
The system SHALL allow an authorized tenant principal to follow a visible policy and create one idempotent consultation request bound to its persisted Party and park grant.

#### Scenario: Replay a policy consultation
- **WHEN** the same Party retries an identical consultation with the same idempotency key
- **THEN** the original local consultation is returned without a duplicate case or any claim of external filing
