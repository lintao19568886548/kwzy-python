## ADDED Requirements

### Requirement: LeaseContract is the aggregate root for tenancy agreements
The system SHALL model a lease as LeaseContract with party_id, park_id, contract_no, start_date, end_date, status, and optional deposit_amount and remark. Party master SHALL remain free of single park_id ownership.

#### Scenario: Contract references party and park
- **WHEN** a lease contract is created
- **THEN** it stores party_id and park_id as foreign references and does not require Party.park_id

### Requirement: Approved lifecycle states
LeaseContract status SHALL be one of DRAFT, PENDING_ACTIVE, ACTIVE, EXPIRING, RENEWED, TERMINATED, BREACHED, CANCELLED with transitions per the approved domain state machine.

#### Scenario: Activate from pending
- **WHEN** an authorized user activates a PENDING_ACTIVE contract whose units are available
- **THEN** status becomes ACTIVE and occupancy is recorded

#### Scenario: Illegal transition rejected
- **WHEN** a client attempts TERMINATED → ACTIVE without a new contract
- **THEN** the API rejects with a business error code

### Requirement: Contract units and terms
A contract MAY have zero or more LeaseContractUnit rows and LeaseTerm rows. Terms types SHALL include INCREASE, RENT_FREE, and OTHER.

#### Scenario: Unit line uniqueness
- **WHEN** two lines for the same contract_id and unit_id are inserted
- **THEN** the database or application rejects the duplicate

### Requirement: Deposit is field-only in this change
deposit_amount MAY be stored and returned. The system SHALL NOT implement deposit refund ledgers, payment allocations, or bill issuance in this change.

#### Scenario: Terminate without refund ledger
- **WHEN** a contract is terminated
- **THEN** occupancy is released and no payment or refund records are required to complete the operation
