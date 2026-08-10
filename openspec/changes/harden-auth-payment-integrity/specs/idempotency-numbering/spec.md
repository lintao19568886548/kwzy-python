## ADDED Requirements

### Requirement: Idempotency-Key for payment create and bill issue
POST /payments and POST /bills/{id}/issue SHALL honor Idempotency-Key per tenant and operation. Identical key and request body replay SHALL return the first result without duplicate side effects. Same key with different body SHALL return 409.

#### Scenario: Payment idempotent replay
- **WHEN** the same Idempotency-Key and body are POSTed twice to /payments
- **THEN** only one payment is created and both responses reference the same payment id

#### Scenario: Different body same key conflicts
- **WHEN** the same Idempotency-Key is reused with any changed business field including remark
- **THEN** the API returns 409 IDEMPOTENCY_KEY_CONFLICT

### Requirement: Idempotent cache never skips authorization
Cache hits SHALL only skip business side effects. On every request the system SHALL re-check action permission, tenant binding, park scope, and resource visibility for the current caller before returning a cached response.

#### Scenario: Cross-park user cannot replay payment cache
- **WHEN** user A with park A creates a payment under key K and user B in the same tenant with only park B replays the same key and body
- **THEN** user B receives 403 or 404 and MUST NOT receive user A's cached payment payload

#### Scenario: Cross-park user cannot replay bill issue cache
- **WHEN** user A issues a bill under key K and user B without park scope for that bill replays the same key
- **THEN** user B receives 403 or 404 and MUST NOT receive the cached bill payload

### Requirement: Full business-body request hash
Payment request hash SHALL cover all PaymentCreate business fields including remark using stable canonical JSON. Secrets such as tokens and passwords MUST NOT be stored.

#### Scenario: Remark-only change conflicts
- **WHEN** two payment requests share an Idempotency-Key and differ only in remark
- **THEN** the second request returns 409 IDEMPOTENCY_KEY_CONFLICT

### Requirement: Idempotency-Key validation
Idempotency-Key when present SHALL be non-empty after trim and at most 128 characters. Invalid keys SHALL return 422 without database DataError.

#### Scenario: Empty or overlong key rejected
- **WHEN** Idempotency-Key is blank or longer than 128 characters
- **THEN** the API returns 422 VALIDATION_ERROR

### Requirement: Concurrent same-key safety on PostgreSQL
Concurrent POST /payments with the same tenant, operation, key, and body SHALL create at most one payment and related allocations. Concurrent same key with different body SHALL surface IDEMPOTENCY_KEY_CONFLICT for at least one request. No request may complete as HTTP 500 solely due to the race.

#### Scenario: Dual connection same key same body
- **WHEN** two PostgreSQL sessions concurrently create payments with identical key and body
- **THEN** only one payment and allocation exist and the idempotency row ends COMPLETED

#### Scenario: Dual connection same key different body
- **WHEN** two PostgreSQL sessions concurrently use the same key with different bodies
- **THEN** at most one payment is created and at least one response is IDEMPOTENCY_KEY_CONFLICT or a stable 409 race code

### Requirement: Concurrent-safe business numbers
contract_no, bill_no, and payment_no generation SHALL use a tenant-scoped sequence store safe under concurrent PostgreSQL writers.

#### Scenario: Parallel payment_no allocation
- **WHEN** concurrent sessions allocate payment numbers for the same tenant and period
- **THEN** generated numbers are unique
