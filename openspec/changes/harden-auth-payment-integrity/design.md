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
- Unique (tenant_id, operation, idempotency_key)
- Store request_hash + response_json without secrets

## Numbering
- number_sequences (tenant_id, biz_type, period_key) with next_val under row lock
