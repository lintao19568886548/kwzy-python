## ADDED Requirements

### Requirement: Structured charge items
A contract MUST support tenant-scoped charge items with unique charge_code, charge_type, calculation_method, billing_cycle, currency, start/end dates, due-day, amount or unit_price, tax_rate and sort order. Supported calculation methods MUST be `FIXED` and `PER_AREA`; supported cycles MUST be `MONTHLY/QUARTERLY/SEMI_ANNUAL/ANNUAL/ONE_TIME`.

#### Scenario: Per-area rent item
- **WHEN** a user defines a monthly RENT item with PER_AREA unit price for a multi-unit contract
- **THEN** preview uses the sum of proposed occupied_area and returns the area, unit price and rounded amount breakdown

#### Scenario: Invalid charge rejected
- **WHEN** a charge has duplicate code, non-positive cycle amount, unsupported currency/method/cycle or dates outside the proposed contract period
- **THEN** submission returns `LEASE_CHARGE_INVALID` and retains the form draft without changing confirmed schedules

### Requirement: Deterministic performance schedule
The system MUST generate a version-bound performance schedule from confirmed charge items using Decimal arithmetic and `ROUND_HALF_UP` to 0.01. Each row MUST include period_start/end, due_date, net/tax/gross amounts, charge/version source and a tenant-unique deterministic key; schedule generation MUST NOT create Bills.

#### Scenario: Same snapshot produces same schedule
- **WHEN** the same canonical contract snapshot is previewed or regenerated
- **THEN** row count, periods, amounts, ordering, checksum and deterministic keys are identical

#### Scenario: One-time charge
- **WHEN** a valid ONE_TIME charge is confirmed
- **THEN** exactly one planned schedule row is produced at its effective/due date

#### Scenario: Empty denominator
- **WHEN** a PER_AREA charge has no positive proposed occupied area
- **THEN** preview fails with `LEASE_CHARGE_AREA_REQUIRED` rather than creating a zero or guessed schedule

### Requirement: Rent-free and escalation rules
Rent-free and escalation rules MUST reference a charge_code and take effect only at a schedule-cycle boundary. Rent-free MUST set eligible contractual charge amounts to zero while retaining their rows and reasons; escalation MUST apply a validated rate or replacement amount from its boundary forward.

#### Scenario: Full-cycle rent-free
- **WHEN** a RENT_FREE rule covers complete monthly cycles for a rent charge
- **THEN** those schedule rows remain present with gross amount zero and an explicit rent-free rule reference

#### Scenario: Partial-cycle rule denied
- **WHEN** rent-free or escalation starts inside an existing cycle
- **THEN** the system returns `LEASE_PRORATION_UNSUPPORTED` and requires an explicit aligned date or separately approved one-time adjustment

#### Scenario: Ordered escalation
- **WHEN** multiple future escalation rules exist for one charge
- **THEN** they apply in effective-date order with no overlap or ambiguity and are included in the version checksum

### Requirement: Downstream billing boundary
Performance schedules MUST be read-only upstream obligations for Billing. Lease MUST expose schedule status and source identifiers but MUST NOT issue, void or allocate Bills; Billing integration MUST later consume each schedule key idempotently.

#### Scenario: Contract activation does not issue bill
- **WHEN** an approved contract activates with confirmed schedules
- **THEN** schedule rows become PLANNED and no Bill, Payment or Allocation row is inserted

#### Scenario: Applied future change preserves past obligations
- **WHEN** a price change applies at a future cycle boundary
- **THEN** past schedule history remains immutable and only future unconsumed schedule projections are superseded by the new version
