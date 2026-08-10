## ADDED Requirements

### Requirement: Payment allocations must match payment park
A payment allocation SHALL only target bills where bill.tenant_id, bill.party_id, and bill.park_id match the payment. Cross-park allocation SHALL fail with PAYMENT_BILL_PARK_MISMATCH and roll back the entire payment transaction.

#### Scenario: Same tenant different parks rejected
- **WHEN** a user with multi-park scope allocates a payment in park A to a bill in park B
- **THEN** the API rejects with PAYMENT_BILL_PARK_MISMATCH and no payment row remains

### Requirement: Concurrent allocations preserve bill paid amount invariants
Bill paid_amount updates under concurrent payments SHALL not exceed total_amount or lose updates. Conflicts SHALL return a stable business 409 error rather than 500.

#### Scenario: Two concurrent payments against one bill
- **WHEN** two PostgreSQL sessions concurrently allocate amounts that together would exceed remaining open amount
- **THEN** at most one excess allocation is rejected and final paid_amount never exceeds total_amount
