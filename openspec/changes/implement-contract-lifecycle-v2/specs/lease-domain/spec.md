## MODIFIED Requirements

### Requirement: LeaseContract is the aggregate root for tenancy agreements
The system MUST keep a stable LeaseContract aggregate id with tenant_id, party_id, park_id, contract_no, contract_type, currency, start/end/effective dates, status, current_version_no and lock_version. Party master MUST remain independent of a single park, and every activated or applied contract version MUST have an immutable canonical snapshot and checksum.

#### Scenario: Create governed draft
- **WHEN** a `lease:write` user creates a contract in an authorized park for an eligible Party
- **THEN** the contract is DRAFT with `lock_version=1`, `current_version_no=0`, a tenant-unique contract number and no immutable active version yet

#### Scenario: Active history cannot be overwritten
- **WHEN** a user attempts to PATCH units, charges, dates or Party on an ACTIVE contract
- **THEN** the system returns `LEASE_CHANGE_ORDER_REQUIRED` and the current projection and prior version snapshots remain unchanged

### Requirement: Approved lifecycle states
New contract writes MUST use `DRAFT/PENDING_APPROVAL/PENDING_ACTIVE/ACTIVE/EXPIRING/EXIT_PENDING/TERMINATED/BREACHED/CANCELLED`. Submission MUST create a domain-managed approval before activation; renewal MUST create a new immutable version on the same root. Legacy `RENEWED` rows MAY be read and migrated but MUST NOT be produced by new commands.

#### Scenario: Submit requires approval
- **WHEN** an authorized user submits a valid DRAFT with the current expected version
- **THEN** the contract becomes PENDING_APPROVAL, a `LEASE_CONTRACT_VERSION` approval and work item are created atomically, and direct activation returns `LEASE_APPROVAL_REQUIRED` until approval

#### Scenario: Approval then activation
- **WHEN** a different authorized approver approves the pending contract and activation invariants pass
- **THEN** the contract becomes PENDING_ACTIVE and activation writes immutable version 1 before projecting ACTIVE occupancy

#### Scenario: Illegal terminal transition rejected
- **WHEN** a client attempts to activate a TERMINATED, BREACHED or CANCELLED contract
- **THEN** the command is rejected with `LEASE_STATUS_INVALID` and no approval, version, occupancy or audit partial write remains

#### Scenario: Legacy renewed compatibility
- **WHEN** migration encounters a legacy contract with status RENEWED
- **THEN** the row remains readable as terminal history and its successor relation is reported, while new renewal APIs never persist a new RENEWED root status

### Requirement: Contract units and terms
A DRAFT contract MUST support multiple distinct current Unit rows and multiple structured charge items. Activation and each applied change MUST validate current units, charges and generated performance schedules, persist their canonical snapshot, and expose legacy `lease_terms` as compatibility data only.

#### Scenario: Multiple unit uniqueness and scope
- **WHEN** a draft contains two or more unit lines
- **THEN** every current unit is unique, current, authorized, in the contract park and has a positive occupied area within capacity

#### Scenario: Terms become governed pricing input
- **WHEN** a draft or change contains charge, rent-free or increase rules
- **THEN** the system validates them through `contract-pricing-schedule`, generates a deterministic preview and includes the confirmed result in the immutable version snapshot

#### Scenario: Failed child replacement rolls back
- **WHEN** any unit, charge or schedule row fails validation or persistence
- **THEN** the contract header, all prior child projections, version, approval and audit records remain unchanged

### Requirement: Deposit is field-only in this change
Deposit amount MUST be stored as a contract/version snapshot and MAY participate in an approved exit-settlement calculation, but Lease MUST NOT create payment, refund, allocation, Bill or accounting entries. Any non-zero financial clearance MUST reference audited evidence from an authorized finance decision.

#### Scenario: Deposit snapshot in exit settlement
- **WHEN** an exit settlement is created for an active contract
- **THEN** it copies the held deposit and outstanding balance as immutable calculation inputs without moving funds

#### Scenario: No implicit refund on close
- **WHEN** a settlement indicates an amount refundable to the Party
- **THEN** the contract remains EXIT_PENDING until clearance evidence is confirmed, and closing the Lease never calls a payment or banking provider
