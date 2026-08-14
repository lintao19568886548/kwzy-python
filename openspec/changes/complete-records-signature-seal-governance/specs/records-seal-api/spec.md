## ADDED Requirements

### Requirement: Strict mounted API surface
The system SHALL mount records, revisions, holds, access, disposition, seals, custody, seal-use, providers and signature-envelope routes under `/api/v1` using strict bodies, bounded pagination, unified envelopes and exact runtime/YAML method parity.

#### Scenario: Unknown field or duplicate parameter
- **WHEN** a client sends an unknown body field or repeated scalar query parameter
- **THEN** the request fails with 422 or 400 before business mutation

### Requirement: Permissions are database derived and separated
The API SHALL enforce distinct read/manage/approve/dispose/custody/use/execute/dispatch/ingest permissions resolved from the database; forged JWT permissions SHALL not expand access.

#### Scenario: Forged seal execute permission
- **WHEN** a user without a database role adds `seal:execute` to a token
- **THEN** execution returns 403 and no receipt exists

### Requirement: Child resources inherit tenant and park scope
Record revisions, holds, requests, confirmations, custody events, receipts, participants and provider events SHALL be addressed through a tenant/park-visible parent. Cross-tenant or out-of-scope ids SHALL return 404.

#### Scenario: Cross-park child id
- **WHEN** a limited user combines an allowed parent id with another park's child id
- **THEN** the API returns 404 without disclosing the child

### Requirement: Commands are idempotent and concurrency safe
Create/submit/execute/confirm/ingest commands SHALL use tenant-scoped idempotency or stable business uniqueness and expected versions. Same-key same-payload replay returns the prior result; changed payload or stale version returns 409.

#### Scenario: Concurrent seal execution
- **WHEN** two workers execute one approved application concurrently
- **THEN** exactly one receipt is committed and the other observes the existing result or a version conflict
