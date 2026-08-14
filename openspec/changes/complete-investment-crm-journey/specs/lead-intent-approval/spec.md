## ADDED Requirements

### Requirement: Immutable versioned intent snapshots
The system SHALL create Lead intent applications whose versions freeze same-park current Units, requested areas, lease period, price proposal, currency, validity and bounded business remarks.

#### Scenario: Draft revision
- **WHEN** an owner edits a DRAFT intent with the expected version
- **THEN** a new immutable version becomes current while prior versions remain queryable

#### Scenario: Unit snapshot mismatch
- **WHEN** a draft references a retired, foreign or stale Unit version or requests invalid area
- **THEN** the command fails atomically and no intent version is created

### Requirement: Approval-center submission
Submitting an intent SHALL create or idempotently reuse a native `LEAD_INTENT` Approval Request from a published matching definition, with a non-PII snapshot and the Lead owner as applicant.

#### Scenario: Submit valid intent
- **WHEN** an authorized owner submits a current valid draft with a unique idempotency key
- **THEN** the intent becomes PENDING and links one approval instance whose tasks, SLA and decisions are managed by the approval center

#### Scenario: Missing published definition
- **WHEN** no applicable published `LEAD_INTENT` definition exists
- **THEN** submission fails closed and the intent remains DRAFT

### Requirement: Approval status is authoritative
Intent detail and every dependent command SHALL derive PENDING, APPROVED, REJECTED, RETURNED or WITHDRAWN state from the linked Approval Request rather than trusting client or stale projection values.

#### Scenario: Fabricated approval status
- **WHEN** a caller supplies APPROVED in a header or request body while the approval instance is pending
- **THEN** lock and conversion commands remain forbidden and no success audit is written

### Requirement: Approved intent gates inventory commitment
Only an unexpired APPROVED intent version covering the same Lead and Unit SHALL authorize a new or renewed exclusive unit lock and subsequent contract-bearing conversion.

#### Scenario: Approval completed after inventory changed
- **WHEN** an approved intent targets a Unit that is no longer current or vacant
- **THEN** lock acquisition returns conflict without changing the approval or inventory history

### Requirement: Intent scope and permissions
Intent reads and writes SHALL enforce tenant, park, owner/manager scope and separate database-derived read, write and submit permissions.

#### Scenario: Other owner reads private intent
- **WHEN** a non-manager Lead user requests another owner's private intent
- **THEN** the request returns no intent, unit, price or approval metadata
