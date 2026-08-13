## ADDED Requirements

### Requirement: Exit handover and settlement draft
An ACTIVE or EXPIRING contract MUST create at most one open exit settlement containing planned handover date, inspection summary, structured meter readings, held-deposit snapshot, Billing outstanding snapshot, receivable/deduction/refund items, calculated net due direction, evidence references and lock_version.

#### Scenario: Create settlement snapshot
- **WHEN** an authorized lease settler starts an exit for an occupying contract
- **THEN** the DRAFT copies current contract/version/units/deposit and scoped outstanding data without releasing occupancy or changing financial records

#### Scenario: Duplicate open settlement blocked
- **WHEN** another open exit settlement already exists for the contract
- **THEN** creation returns `LEASE_EXIT_IN_FLIGHT` 409 and the existing settlement summary

#### Scenario: Invalid meter or amount rejected
- **WHEN** a meter reading regresses without reason or an item amount is negative/has an unsupported type
- **THEN** the draft command returns `LEASE_EXIT_ITEM_INVALID` and preserves the prior settlement version

### Requirement: Deterministic exit totals
Settlement totals MUST use Decimal and `ROUND_HALF_UP` to 0.01. Receivables and approved deductions MUST reduce refundable deposit; the response MUST separately expose `net_due_from_party` and `net_due_to_party`, never a signed ambiguous balance.

#### Scenario: Deposit covers charges
- **WHEN** held deposit exceeds all approved receivable and deduction items
- **THEN** net_due_to_party equals the remaining refundable amount and net_due_from_party is zero

#### Scenario: Charges exceed deposit
- **WHEN** approved receivables and deductions exceed held deposit
- **THEN** net_due_from_party equals the shortfall and net_due_to_party is zero

#### Scenario: Recalculation is stable
- **WHEN** the same sorted settlement items and snapshots are recalculated
- **THEN** totals and checksum are identical and no Payment, refund, allocation or Bill row is created

### Requirement: Exit approval and financial clearance
Exit settlement MUST move through `DRAFT→SUBMITTED→APPROVED→CLOSED` or `REJECTED/WITHDRAWN`. Submission MUST move the Lease to EXIT_PENDING while retaining occupancy. A non-zero net amount MUST require `financial_clearance_status=CONFIRMED`, evidence attachment/reference and an authorized audited reason before close.

#### Scenario: Approval keeps units occupied
- **WHEN** an exit settlement is submitted or approved
- **THEN** the Lease remains in the occupying set and Unit used_area is unchanged

#### Scenario: Non-zero balance lacks evidence
- **WHEN** a user tries to close an approved settlement with a non-zero net amount and no confirmed evidence
- **THEN** it returns `LEASE_FINANCIAL_CLEARANCE_REQUIRED` and keeps the contract EXIT_PENDING

#### Scenario: Clearance records fact only
- **WHEN** a finance-authorized user confirms external settlement evidence
- **THEN** the system stores reference, actor and timestamp but does not call a bank, payment, refund or accounting provider

### Requirement: Atomic settlement close
Closing an approved and cleared settlement MUST lock the Lease and affected Units, validate expected versions, append a terminal contract version, set settlement CLOSED and Lease TERMINATED, release occupancy, close work items and audit in one idempotent transaction.

#### Scenario: Successful exit close
- **WHEN** every handover, approval, document and clearance gate passes
- **THEN** the terminal version and closed settlement are visible, affected Units are recomputed and the Party contract profile no longer counts the Lease as current

#### Scenario: Close rollback
- **WHEN** Unit, version, work-item or audit persistence fails during close
- **THEN** settlement remains APPROVED, Lease remains EXIT_PENDING, occupancy remains effective and no partial terminal version exists

#### Scenario: Close replay
- **WHEN** the same close command is retried with its original idempotency key
- **THEN** it returns the original CLOSED result without another terminal version or occupancy release

### Requirement: Breach and cancellation distinction
Cancellation MUST apply only before activation and require no exit settlement. Breach after activation MUST preserve occupancy until an approved exit settlement closes, while recording the breach reason and effective date in the terminal version.

#### Scenario: Draft cancellation
- **WHEN** an authorized user cancels a DRAFT or rejected contract
- **THEN** status becomes CANCELLED, open approval/doc todos close and no version, occupancy or settlement is created

#### Scenario: Active breach
- **WHEN** an active contract is marked for breach termination
- **THEN** it enters EXIT_PENDING with breach context and does not release Units until settlement close
