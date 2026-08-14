# lease-domain Specification

## Purpose
定义 LeaseContract 聚合、合同单元与条款行、基础生命周期和押金字段边界。该规格确保合同与 Party 主档解耦，合同状态迁移受控，并明确基础阶段不产生押金退款、核销或账单副作用。
## Requirements
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

### Requirement: Lease signing delegates to governed envelope truth
An APPROVED lease document SHALL create or reference an electronic-signature envelope bound to its exact checksum. A local/sandbox result SHALL NOT append a legal `SIGNED` lease document version. Only a `COMPLETED` envelope with `live_verified=true` MAY produce a `SIGNED` version.

#### Scenario: Local sign command
- **WHEN** an APPROVED lease document is signed through the local sandbox provider
- **THEN** a SANDBOX_COMPLETED envelope is recorded and the lease document remains APPROVED

### Requirement: Lease activation uses truthful document evidence
Any lease rule that requires signed evidence SHALL distinguish approved, sandbox-completed and live-verified signed documents. Sandbox evidence MAY satisfy local test setup only when explicitly configured, and SHALL be identified in responses and audit.

#### Scenario: Production activation with sandbox evidence
- **WHEN** production activation requires a signed contract but only sandbox evidence exists
- **THEN** activation fails closed with a provider/evidence error
