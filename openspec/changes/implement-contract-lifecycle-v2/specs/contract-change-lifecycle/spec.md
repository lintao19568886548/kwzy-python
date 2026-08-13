## ADDED Requirements

### Requirement: Typed contract change orders
The system MUST represent renewal, expansion, reduction, unit transfer, price adjustment, Party transfer and early termination as typed change-order aggregates with reason, effective_date, base_version_no, lock_version and a schema-versioned complete proposed contract snapshot.

#### Scenario: Create renewal proposal
- **WHEN** a lease changer proposes a renewal from an ACTIVE or EXPIRING contract
- **THEN** the draft contains the current snapshot plus explicit new dates/charges, references the current base version and does not modify the Lease root

#### Scenario: Unsupported patch rejected
- **WHEN** a proposal includes a field not allowed for its change type or omits a required reason/effective value
- **THEN** it returns `LEASE_CHANGE_INVALID` and creates no partial change or audit record

### Requirement: Type-specific invariants
Each change type MUST validate its complete future state: renewal extends the contractual period; expansion adds capacity; reduction removes or decreases capacity without negative area; transfer replaces units in the same park; price adjustment changes only future cycle-boundary charges; Party transfer references an eligible Party; early termination creates an exit-settlement path rather than releasing occupancy immediately.

#### Scenario: Retroactive price adjustment denied
- **WHEN** a user proposes a price adjustment effective before today or outside a charge-cycle boundary
- **THEN** the system rejects it with `LEASE_CHANGE_EFFECTIVE_DATE_INVALID` and preserves existing schedule rows

#### Scenario: Party transfer is scoped
- **WHEN** a Party-transfer proposal references an archived, blacklisted, foreign-tenant or park-ineligible Party
- **THEN** the proposal is rejected without revealing foreign Party details

#### Scenario: Early termination waits for settlement
- **WHEN** an approved EARLY_TERMINATION change reaches its effective date
- **THEN** the contract enters EXIT_PENDING and links an exit settlement while current occupancy remains effective until settlement close

### Requirement: Approval and versioned application
A change MUST move through `DRAFT→SUBMITTED→APPROVED→APPLIED` or `REJECTED/WITHDRAWN/CANCELLED`. Apply MUST lock the current contract, require the same base version and effective date, validate the approved proposal again, insert exactly one immutable next version and update all projections atomically.

#### Scenario: Approved change becomes stale
- **WHEN** another authorized change has advanced the Lease current_version_no before apply
- **THEN** apply returns `LEASE_CHANGE_BASE_VERSION_CONFLICT` 409 and the approved change remains unapplied for explicit rebase or cancellation

#### Scenario: Successful unit transfer
- **WHEN** a due, approved transfer with a current base version passes Unit locks and capacity checks
- **THEN** one new version, current unit/charge/schedule projections, occupancy updates, change APPLIED state and audit commit together

#### Scenario: Apply failure rolls back
- **WHEN** version, schedule, occupancy, work-item or audit persistence fails during apply
- **THEN** the Lease, change, Units, approval and all current projections remain exactly as before the command

### Requirement: Single in-flight change and idempotent replay
The system MUST permit at most one SUBMITTED or APPROVED unapplied change per contract and MUST scope idempotency keys by tenant and command. Drafts MAY coexist, but submission MUST resolve the exclusivity rule.

#### Scenario: Concurrent submissions
- **WHEN** two draft changes for one contract are submitted concurrently
- **THEN** PostgreSQL accepts exactly one in-flight change and returns `LEASE_CHANGE_IN_FLIGHT` 409 for the other

#### Scenario: Replay applied command
- **WHEN** the same approved change apply is retried with its original idempotency key
- **THEN** the original applied version is returned and no duplicate version, occupancy delta or audit event is added

### Requirement: Complete change timeline
Contract detail MUST expose ordered change, approval, application and version lineage with actor, reason, timestamps and sanitized before/after summaries while preserving rejected and withdrawn decisions.

#### Scenario: Rejected proposal remains auditable
- **WHEN** an approver rejects a submitted price adjustment
- **THEN** current contract state is unchanged and detail shows the rejected proposal, decision reason and approval events without exposing unrelated approvals
