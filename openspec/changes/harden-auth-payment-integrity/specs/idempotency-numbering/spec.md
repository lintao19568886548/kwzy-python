## ADDED Requirements

### Requirement: Idempotency-Key for payment create and bill issue
POST /payments and POST /bills/{id}/issue SHALL honor Idempotency-Key per tenant and operation. Identical key and request body replay SHALL return the first result without duplicate side effects. Same key with different body SHALL return 409.

#### Scenario: Payment idempotent replay
- **WHEN** the same Idempotency-Key and body are POSTed twice to /payments
- **THEN** only one payment is created and both responses reference the same payment id

### Requirement: Concurrent-safe business numbers
contract_no, bill_no, and payment_no generation SHALL use a tenant-scoped sequence store safe under concurrent PostgreSQL writers.

#### Scenario: Parallel payment_no allocation
- **WHEN** concurrent sessions allocate payment numbers for the same tenant and period
- **THEN** generated numbers are unique
