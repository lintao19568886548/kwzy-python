## ADDED Requirements

### Requirement: Domain-managed approvals
Initial contract submission, contract-change submission and exit-settlement submission MUST create approval requests through a commit-free Approval port and MUST apply decisions through Lease domain commands so approval events and business state share one transaction.

#### Scenario: Contract approval succeeds
- **WHEN** an eligible approver approves a PENDING_APPROVAL contract with the current expected version
- **THEN** approval becomes APPROVED, the contract becomes PENDING_ACTIVE, related approval work is closed and both audit records commit together

#### Scenario: Generic decision is fail-closed
- **WHEN** a caller tries to decide a Lease-managed approval through the generic workflow command
- **THEN** it returns `APPROVAL_DOMAIN_COMMAND_REQUIRED` and no approval or Lease state changes

#### Scenario: Withdraw pending request
- **WHEN** the original applicant withdraws a still-pending request with the current version
- **THEN** approval becomes WITHDRAWN, the business aggregate returns to its editable state and the work item closes atomically

### Requirement: Segregation of duties
An approver MUST have both `approval:decide` and `lease:approve`, MUST be in the contract park scope and MUST NOT approve their own request unless they also have `lease:approve_override` and provide a non-empty override reason.

#### Scenario: Self approval blocked
- **WHEN** an applicant without override permission approves their own contract or change
- **THEN** the command returns `LEASE_SELF_APPROVAL_FORBIDDEN` 403 and preserves pending state

#### Scenario: Authorized override audited
- **WHEN** an administrator with override permission self-approves using a reason
- **THEN** the decision succeeds and audit records the override flag and sanitized reason

### Requirement: Versioned contract documents
The system MUST link attachment metadata to contract id and optional contract version, change or exit settlement with document_type, document_version, SHA-256 checksum and `DRAFT/APPROVED/SIGNED/VOID` status. Binary content MUST remain owned by the attachments context.

#### Scenario: Approve main contract document
- **WHEN** a lease document manager approves an active attachment as the current MAIN_CONTRACT document
- **THEN** a versioned document record is appended and any prior current draft is retained or explicitly VOID, never overwritten

#### Scenario: Foreign attachment denied
- **WHEN** a request references an attachment from another tenant, park or business aggregate
- **THEN** it returns 404 and creates no document metadata

#### Scenario: Activation document gate
- **WHEN** a PENDING_ACTIVE contract lacks an APPROVED or externally verified SIGNED main contract document
- **THEN** activation returns `LEASE_DOCUMENT_REQUIRED` and does not occupy Units

### Requirement: External signing remains fail-closed
Electronic signature, OCR and archive-provider calls MUST use explicit ports. Local/test fakes MUST be labeled simulated; production without complete provider configuration MUST return 503 and MUST NOT set externally SIGNED or VERIFIED state.

#### Scenario: Provider is not configured
- **WHEN** production requests external signing without endpoint, credential or verification configuration
- **THEN** the command returns `SIGNATURE_PROVIDER_NOT_CONFIGURED` 503 and document status remains unchanged

#### Scenario: Fake signature is visible
- **WHEN** a local acceptance fixture completes the fake signature flow
- **THEN** the response and audit mark provider=`fake` and `live_verified=false`, preventing a LIVE claim

### Requirement: Governance timeline and work items
Approval, document review, signature wait, change effective-date and exit-settlement actions MUST create or close idempotent WorkItems and appear in one ordered contract governance timeline.

#### Scenario: Rejected change closes approval todo
- **WHEN** a submitted change is rejected
- **THEN** its pending approval todo closes, the rejection remains in timeline and no activation/change-effective todo is left open
