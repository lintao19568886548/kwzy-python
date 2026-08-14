# payment-allocation Specification

## Purpose
TBD - created by archiving change complete-receivables-collection-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Payment exposes authoritative unapplied balance
The API SHALL derive allocated and unapplied amounts from active allocation history. A confirmed Payment MAY be wholly unapplied, partially applied or applied to multiple Bills; client-supplied balances are forbidden.

#### Scenario: Overpayment retained as prepayment
- **WHEN** a CNY 1200 Payment allocates CNY 1000 to Bills
- **THEN** the Payment reports allocated 1000 and unapplied 200 without altering any unrelated Bill

### Requirement: Unapplied money can be allocated later
An authorized caller SHALL allocate remaining Payment balance to one or many same-tenant, same-park, same-Party open Bills using an Idempotency-Key. Payment and Bills SHALL be locked in stable order and over-allocation SHALL fail atomically.

#### Scenario: Later multi-bill allocation
- **WHEN** unapplied balance covers two open Bills and a valid allocation request names both
- **THEN** both Bills update in one transaction and the Payment balance decreases by the exact sum

### Requirement: Allocation history is immutable and reversible
Normal flows SHALL not edit or delete allocation rows. Full Payment reversal SHALL apply compensating Bill deltas once, mark Payment reversed and retain original allocations for audit.

#### Scenario: Concurrent double reversal
- **WHEN** two transactions reverse the same Payment
- **THEN** at most one succeeds and Bill paid amounts are deducted exactly once

### Requirement: Allocation never crosses authority boundaries
Every target Bill SHALL be tenant/park-visible and belong to the Payment Party and park. Mixed currency, void/draft/discarded Bills, duplicate request bodies or parameter pollution SHALL be rejected without partial writes.

#### Scenario: Cross-park Bill id
- **WHEN** one allocation references a Bill outside the Payment park
- **THEN** the whole request fails and no allocation or Bill delta is committed
