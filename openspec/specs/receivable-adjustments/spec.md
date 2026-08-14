# receivable-adjustments Specification

## Purpose
TBD - created by archiving change complete-receivables-collection-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Risk and money treatments require approval
Waiver, extension, bad-debt, dispute and dispute-resolution requests SHALL create immutable request intent plus a shared ApprovalRequest snapshot. No financial amount, effective due date or collection hold may change before approval is `APPROVED`. Opening and resolving a dispute SHALL be separately approved actions.

#### Scenario: Apply pending waiver
- **WHEN** a caller tries to apply a waiver whose approval is pending
- **THEN** the API returns an approval-required conflict and Bill amounts remain unchanged

### Requirement: Adjustment effects are bounded and stale-safe
Waiver/bad-debt amount SHALL be positive and no greater than current collectible open amount; extension SHALL move effective due date forward; dispute SHALL carry a reason. Apply SHALL lock the Bill and compare the submitted Bill lock/open snapshot before committing.

#### Scenario: Payment arrives during approval
- **WHEN** a Payment changes open amount after an adjustment was submitted
- **THEN** stale adjustment apply fails and requires a new reviewed request

#### Scenario: Resolve an open dispute
- **WHEN** a dispute-resolution request is approved and its Bill snapshot is still current
- **THEN** the collection hold is removed and the Bill dispute state becomes `RESOLVED`

### Requirement: Applied treatments remain separately reportable
Bill reads SHALL separately expose original total, paid, approved waiver, approved bad-debt, collectible open amount, effective due date and dispute/hold state. A waived or written-off receivable SHALL not be mislabeled as cash paid.

#### Scenario: Full approved bad debt
- **WHEN** remaining collectible amount is written off
- **THEN** cash paid remains unchanged, bad-debt amount increases and collectible open becomes zero

### Requirement: Adjustments are auditable and non-destructive
Requests and applied effects SHALL keep applicant, approval id, reason, timestamps and audit events. Normal application APIs SHALL not physically delete adjustment history.

#### Scenario: Rejected extension
- **WHEN** the shared approval rejects an extension
- **THEN** the request remains queryable as rejected and the effective due date is unchanged
