# Design

## Auth
- Allowed env: local | test | staging | production (case-insensitive normalize)
- Invalid env: settings validation fails at startup
- Anonymous context only if allow_anon_dev AND env in {local, test}
- staging/production always require JWT

## Payment integrity
- Reject allocation when bill.park_id != payment.park_id → PAYMENT_BILL_PARK_MISMATCH
- SELECT bill FOR UPDATE ordered by bill_id before deltas
- reverse locks payment then bills by id order

## Idempotency
- Unique (tenant_id, operation, idempotency_key); user_id stored for audit only, not isolation
- Store request_hash + response_json without secrets
- Request hash for payments covers full PaymentCreate business fields (including remark)
- **Authorization re-check always precedes cache return**:
  - Payment: permission + park scope + party + each allocation bill visibility first
  - Bill issue: permission + scoped `_require(bill_id)` first
  - Cache hit reloads resource under current scope (get_payment / get_bill)
- Idempotency-Key: optional; when present length 1–128 after trim
- Concurrent first-insert uses unique constraint + PROCESSING → COMPLETED; conflicts map to 409 not 500

## Numbering
- number_sequences (tenant_id, biz_type, period_key) with next_val under row lock
- Dead count()+1 helpers removed from payment/bill/lease repositories
