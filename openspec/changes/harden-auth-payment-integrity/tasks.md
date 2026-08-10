# Tasks: harden-auth-payment-integrity

- [x] OpenSpec artifacts
- [x] Auth fail-closed config + deps + tests
- [x] Payment park match + FOR UPDATE + reverse locking
- [x] idempotency_keys + number_sequences migration
- [x] Wire payment/bill/lease numbering + Idempotency-Key
- [x] OpenAPI sync
- [x] PG concurrent tests + full pytest + push branch
- [x] Idempotency cache must re-check authorization (park scope)
- [x] Full PaymentCreate body hash including remark
- [x] Idempotency-Key length validation + OpenAPI min/max
- [x] PG dual-connection concurrent same-key tests
- [x] Remove dead next_seq / next_contract_seq count+1 helpers
- [x] Idempotent replay returns first response_json (not current state after reverse/void)
