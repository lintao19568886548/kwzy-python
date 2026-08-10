## ADDED Requirements

### Requirement: Current risk status on Party
parties.risk_status SHALL be NORMAL or BLACKLISTED for fast queries and SHALL be independent of lifecycle status ACTIVE, INACTIVE, or ARCHIVED.

#### Scenario: Active and blacklisted
- **WHEN** an ACTIVE party is blacklisted
- **THEN** status remains ACTIVE and risk_status is BLACKLISTED

### Requirement: Immutable risk event history table
The first Party release SHALL include party_risk_events with at least id, tenant_id, party_id, event_type, previous_risk_status, new_risk_status, reason, operator_user_id, request_id, source, occurred_at, and created_at. event_type SHALL include BLACKLISTED and BLACKLIST_REMOVED.

#### Scenario: Blacklist appends event
- **WHEN** a party is blacklisted
- **THEN** a party_risk_events row is inserted and existing events are not updated

### Requirement: Risk events are append-only
party_risk_events rows SHALL NOT be updated or deleted in normal application flows.

#### Scenario: No update API for events
- **WHEN** Party APIs are designed
- **THEN** there is no endpoint to edit or delete risk events

### Requirement: Same-transaction state event and audit
Changing risk_status SHALL occur in one transaction with inserting the risk event and writing audit_logs. audit_logs and party_risk_events SHALL both be written and SHALL NOT substitute for each other.

#### Scenario: Transaction includes both stores
- **WHEN** blacklist commits
- **THEN** risk_status, party_risk_events, and audit_logs are committed together

### Requirement: Reason required for blacklist and removal
Blacklist and blacklist removal operations SHALL require a non-empty reason.

#### Scenario: Missing reason rejected
- **WHEN** blacklist is called without reason
- **THEN** the request fails with PARTY_RISK_REASON_REQUIRED or equivalent

### Requirement: Dedicated risk permissions
The system SHALL use party:risk_read to read full risk reasons and risk-events timelines, and party:risk_manage to perform blacklist and remove-blacklist. Ordinary party:read SHALL NOT by default expose full risk reasons.

#### Scenario: Read without risk_read
- **WHEN** a user has party:read but not party:risk_read
- **THEN** full risk event reasons are not returned by default

### Requirement: Dedicated risk APIs not generic patch
Risk status changes SHALL use dedicated endpoints such as POST blacklist and POST remove-blacklist and SHALL NOT be performed via generic PATCH of risk_status.

#### Scenario: No patch risk_status
- **WHEN** client PATCHes risk_status on Party update
- **THEN** the design does not treat that as the supported risk mutation path

### Requirement: Archive restore does not clear blacklist
Restoring an ARCHIVED Party SHALL NOT automatically clear BLACKLISTED risk_status or rewrite risk history. Risk history for archived parties SHALL be retained.

#### Scenario: Restore keeps blacklist
- **WHEN** a blacklisted archived party is restored
- **THEN** risk_status remains BLACKLISTED unless a separate risk_manage action is performed

### Requirement: Lease signing rules deferred
Future Lease modules may use current risk_status; this Party design stage SHALL NOT implement Lease signing denial.

#### Scenario: No lease code required
- **WHEN** Party design is approved
- **THEN** no Lease implementation is required by this capability
