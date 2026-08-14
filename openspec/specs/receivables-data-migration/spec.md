# receivables-data-migration Specification

## Purpose
TBD - created by archiving change complete-receivables-collection-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Synthetic migration covers legacy receivables evidence
The migration rehearsal SHALL map legacy amount-bill headers/fee components, receipt amount/time and rent-verification confirmation/abnormal state into Bill, BillLine, receipt/Payment/allocation or exception records without copying implicit finance double-writes.

#### Scenario: Receipt without authoritative Bill match
- **WHEN** a legacy receipt row cannot be matched uniquely to a migrated Bill and Party
- **THEN** it enters quarantine/pending review and is not auto-allocated

### Requirement: Migration is dry-runnable, transactional and resumable
Dry-run SHALL report mappings, quarantine and reconciliation without writes. Apply SHALL be transactional per checkpoint and injected interruption SHALL leave no partial checkpoint. Reapply SHALL create no duplicate financial documents.

#### Scenario: Interrupted receipt batch
- **WHEN** apply stops after staging receipts but before checkpoint commit
- **THEN** the checkpoint rolls back and a resumed run processes each source row once

### Requirement: Reconciliation distinguishes cash and treatment
Reconciliation SHALL compare record counts, original receivable, paid cash, waived, bad debt, collectible open, exception counts, orphan/FK counts and deterministic checksums by tenant/park/period. Differences SHALL be explicit and no raw account/phone/PII appears in evidence.

#### Scenario: Paid total mismatch
- **WHEN** migrated Payment allocations do not equal the mapped authoritative receipt amount
- **THEN** reconciliation fails with a bounded source reference and aggregate difference

### Requirement: Real-data readiness remains blocked without source evidence
Synthetic success SHALL NOT be called real migration PASS. Authorized legacy schema dump, desensitized sample, source-system freeze point, Party/park/contract mapping and signed reconciliation are required before cutover.

#### Scenario: No legacy snapshot
- **WHEN** every synthetic test passes but no authorized legacy snapshot exists
- **THEN** status is synthetic-ready and real-data migration remains BLOCKED
