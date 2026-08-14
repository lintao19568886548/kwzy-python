## ADDED Requirements

### Requirement: Seal registry is typed and scoped
The system SHALL maintain tenant-unique seal codes with kind `OFFICIAL/CONTRACT/FINANCE/LEGAL_REPRESENTATIVE/ELECTRONIC/OTHER`, optional park, custodian, status `ACTIVE/TRANSFER_PENDING/SUSPENDED/LOST/RETIRED` and optimistic version.

#### Scenario: Duplicate seal code
- **WHEN** two seals in one tenant use the same normalized code
- **THEN** PostgreSQL rejects the duplicate without leaking another tenant's row

### Requirement: Custody changes are acceptance based
Custody transfer SHALL record proposer, current custodian, intended custodian, reason and timestamp. Current custody SHALL change only when the intended custodian accepts the pending transfer under the expected seal version.

#### Scenario: Unrelated user accepts transfer
- **WHEN** a user other than the intended custodian accepts a transfer
- **THEN** the operation is denied and custody remains unchanged

### Requirement: Loss and retirement preserve history
Loss SHALL suspend use immediately and append an event. Retirement SHALL be reasoned and blocked by pending transfers, approved unexecuted uses or open signature envelopes. No physical DELETE route SHALL exist.

#### Scenario: Retire seal with approved use
- **WHEN** a manager retires a seal referenced by an approved unexecuted application
- **THEN** retirement is rejected and the application remains executable by policy

### Requirement: Custody history is append-only
Every create, transfer request, transfer acceptance, suspension, loss, recovery and retirement SHALL append a tenant/park-scoped custody event with actor and safe before/after facts.

#### Scenario: Query history across park scope
- **WHEN** a limited user requests history for a seal outside allowed parks
- **THEN** the API returns 404
