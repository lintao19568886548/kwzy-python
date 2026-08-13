## ADDED Requirements

### Requirement: Scoped tenant contract profile
The system MUST provide a Party-centered contract profile containing eligible Party summary, current and historical contracts, authorized parks, current units, contract versions, charge/schedule summary, changes, approvals, documents, exit settlements and scoped Billing outstanding snapshot.

#### Scenario: Multi-contract Party
- **WHEN** an authorized user opens a Party that has current and historical contracts across allowed parks
- **THEN** the profile returns stable grouped sections and links each fact to its source contract/version without flattening contracts into Party fields

#### Scenario: Cross-park data omitted
- **WHEN** the Party has a contract in a park outside the user's scope
- **THEN** that contract and its counts, amounts, documents and timeline are absent rather than masked as a discoverable row

### Requirement: Reconciled operational indicators
Profile and contract summary MUST use the same scoped filters and return current-contract count, occupied area, scheduled gross amount, upcoming expiries, pending approvals, due changes, exit-pending count and unresolved clearance count with explicit as-of time and zero-denominator behavior.

#### Scenario: Summary reconciles with list
- **WHEN** the same park, Party, status and date filters are used for summary and contract list
- **THEN** status counts reconcile to visible contracts and scheduled amounts reconcile to visible current-version schedule rows

#### Scenario: Empty profile
- **WHEN** an eligible Party has no visible contract
- **THEN** all counts and amounts are zero, optional durations are null and no division or missing-key error occurs

### Requirement: Stable filters and ordering
Contract list/profile queries MUST support park, Party, status, contract type, keyword, expiry range, approval state, change state and exit state with deterministic ordering by business date and id, plus bounded pagination.

#### Scenario: Concurrent insert pagination
- **WHEN** a new contract is inserted while a client pages through a stable sort
- **THEN** each response preserves documented ordering and never returns an unordered database-dependent sequence

### Requirement: Minimal PII and source transparency
Profile responses and exports MUST expose only fields allowed by Party and Lease permissions and MUST label schedule, outstanding, document and external-source data with source/as-of/readiness. Raw identity documents, attachment content, external secrets and quarantined legacy PII MUST never enter profile payloads.

#### Scenario: Read-only profile
- **WHEN** a user has `lease:read` but lacks Party-sensitive or attachment permissions
- **THEN** they see permitted business names and contract facts while sensitive contacts/documents are omitted and no write controls are authorized
