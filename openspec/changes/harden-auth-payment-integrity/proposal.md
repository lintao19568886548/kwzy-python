# Change: harden-auth-payment-integrity

## Why
Post-merge acceptance found P0 auth fail-open on non-lowercase production APP_ENV, P1 cross-park payment allocation, concurrent paid_amount lost updates, missing Idempotency-Key and concurrent-unsafe number generation.

## What
- Fail-closed auth with normalized APP_ENV whitelist and ALLOW_ANON_DEV gate
- Payment same-park allocation + FOR UPDATE concurrency
- idempotency_keys + number_sequences tables and wiring
- OpenAPI/spec alignment for payments

## Out
- Online payment gateway, refunds, collection cases, ETL, merge main
