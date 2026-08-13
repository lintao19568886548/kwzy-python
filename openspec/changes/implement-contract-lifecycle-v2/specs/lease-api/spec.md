## MODIFIED Requirements

### Requirement: Nested REST API under /api/v1
Lease lifecycle, versions, changes, charges, documents, approvals, exit settlements, summary and tenant-profile APIs MUST be exposed under `/api/v1` with the unified `{code,message,data}` envelope, stable AppError codes and `X-Request-Id` propagation. Every business write MUST require `expected_version` and commands with retry risk MUST accept an idempotency key.

#### Scenario: List requires lease read
- **WHEN** a user without `lease:read` calls any contract list, summary, detail, version or tenant-profile endpoint
- **THEN** the API returns 403 without contract counts or identifiers

#### Scenario: Stale command
- **WHEN** two requests use the same expected version to submit, edit, apply a change or close a settlement
- **THEN** only one commits and the other returns `LEASE_VERSION_CONFLICT` 409 with the minimal latest version summary

#### Scenario: Idempotent command replay
- **WHEN** a client repeats a successful change-apply or settlement-close request with the same tenant-scoped idempotency key and payload
- **THEN** the API returns the original result without adding a version, schedule, occupancy or audit duplicate

### Requirement: Tenant and park scope
All Lease queries, selectors, aggregates and writes MUST enforce tenant_id from TenantContext and the contract park scope. Empty park scope MUST deny park-scoped data; Party, Unit, approval, document and settlement references MUST be revalidated in the same tenant and authorized park.

#### Scenario: Cross-tenant child reference hidden
- **WHEN** a tenant A command references a Party, Unit, change, document, approval or settlement belonging to tenant B
- **THEN** the API returns 404 and does not reveal whether the foreign resource exists

#### Scenario: Mixed-park aggregate excludes unauthorized contracts
- **WHEN** a park-limited user requests summary or Party contract profile
- **THEN** counts, amounts and detail contain only allowed parks and do not reveal excluded park totals

### Requirement: Audit and logging without secrets
Every successful contract, version, change, approval, document and exit-settlement write MUST append a transaction-bound audit record and structured business log with request_id, tenant_id, user_id, park_id, action and resource id. Logs and audit detail MUST exclude raw identity documents, attachment bytes, full phone/address PII, signatures and provider secrets.

#### Scenario: Change apply audited atomically
- **WHEN** an approved change is applied
- **THEN** one business audit links the prior/new version, change and affected unit ids, and any failure rolls back both business state and audit

#### Scenario: Sensitive document metadata
- **WHEN** document or signature state changes
- **THEN** logs include document type, checksum prefix and status but never binary content, signed URL, certificate body or secret credential

## ADDED Requirements

### Requirement: Authorized selectors and reconciled detail
The API MUST provide authorized Park, Party and current Unit selector data and a reconciled contract detail containing current projection, immutable versions, change/approval timeline, charges, schedules, documents and exit state without requiring clients to submit hidden internal ids they cannot discover.

#### Scenario: Create form selector
- **WHEN** a lease writer opens a create form for an authorized park
- **THEN** selectors return eligible Parties and current Units in that park with human-readable labels and exclude archived/blacklisted Parties and unavailable Units

### Requirement: Domain-managed approval endpoint
Approving or rejecting `LEASE_CONTRACT_VERSION`, `LEASE_CHANGE_ORDER` or `LEASE_EXIT_SETTLEMENT` MUST use the corresponding Lease domain command. The generic approval decision endpoint MUST fail closed for those business types.

#### Scenario: Generic approval is refused
- **WHEN** a client calls generic `/approvals/{id}/approve` for a Lease-managed approval
- **THEN** it returns `APPROVAL_DOMAIN_COMMAND_REQUIRED` 409 and neither approval nor contract state changes
