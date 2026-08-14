# party-enterprise-risk-profile Specification

## Purpose
TBD - created by archiving change complete-party-enterprise-profile.

## Requirements

### Requirement: Enterprise risk signals are append-only local facts
The system SHALL record enterprise risk signals with category `LEGAL/FINANCIAL/COMPLIANCE/OPERATIONAL/REPUTATION/OTHER`, severity `LOW/MEDIUM/HIGH/CRITICAL`, safe summary, occurred time, source type/reference, optional evidence attachment, creator and created time. Normal APIs SHALL NOT update or delete a signal.

#### Scenario: Signal correction
- **WHEN** an operator discovers that a risk signal is incorrect
- **THEN** the original signal remains immutable and the operator resolves it with a separate resolution record

### Requirement: Risk source references are idempotent
Non-empty source type/reference pairs SHALL be unique per tenant and Party. Replaying the same migration/provider event SHALL return the existing signal without duplicating risk counts.

#### Scenario: Duplicate source event
- **WHEN** the same source reference is applied twice
- **THEN** one risk signal exists and the summary counts it once

### Requirement: Risk resolution is separately audited
Resolving a signal SHALL require `party:risk_manage`, a non-empty reason and the current signal state. The system SHALL append one resolution with resolver and time in the same transaction as audit; concurrent second resolution SHALL be idempotent or conflict.

#### Scenario: Concurrent resolution
- **WHEN** two reviewers resolve the same signal concurrently
- **THEN** at most one resolution is committed and no risk history is overwritten

### Requirement: Current enterprise risk summary is deterministic
The current summary SHALL derive unresolved counts by severity/category and overall level equal to the highest unresolved severity, or `NONE` when none remain. The response SHALL state that this is a local signal summary, not an external credit score.

#### Scenario: Highest unresolved severity
- **WHEN** an organization has unresolved LOW and HIGH signals and a resolved CRITICAL signal
- **THEN** the current overall level is HIGH and the resolved CRITICAL signal remains only in history

### Requirement: Blacklist remains an independent explicit control
Derived enterprise risk SHALL NOT automatically change `Party.risk_status`, create or remove blacklist events, approve/reject workflows, or block a contract. Existing blacklist operations and permissions remain authoritative for `NORMAL/BLACKLISTED`.

#### Scenario: Critical signal added
- **WHEN** a CRITICAL enterprise signal is created
- **THEN** the risk summary becomes CRITICAL while Party blacklist status is unchanged

### Requirement: Full risk detail has dedicated permissions
Only callers with `party:risk_read` SHALL receive signal summaries, source references, attachment ids and resolution reasons. Ordinary Party readers MAY receive only the existing blacklist flag.

#### Scenario: Risk detail hidden
- **WHEN** a party:read-only caller opens an enterprise Party
- **THEN** the response does not include local risk level, signal counts or source details
