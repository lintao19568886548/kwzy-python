# records-classification-retention Specification

## Purpose
TBD - created by archiving change complete-records-signature-seal-governance. Update Purpose after archive.
## Requirements
### Requirement: Categories define controlled archive policy
The system SHALL maintain tenant-unique category codes with name, confidentiality allowance, retention mode `YEARS/PERMANENT`, positive retention years when applicable, lifecycle status and optimistic version. Published use of a category SHALL snapshot its policy on each filed record.

#### Scenario: Category policy changes after filing
- **WHEN** retention years are changed after a record was filed
- **THEN** the filed record keeps its original retention snapshot and new records use the new policy

### Requirement: Record numbers are deterministic and unique
The system SHALL allocate a server-owned record number by tenant, category and year under concurrency, and SHALL enforce tenant-unique record numbers in PostgreSQL.

#### Scenario: Concurrent record creation
- **WHEN** two transactions allocate records for the same category and year
- **THEN** they receive distinct monotonic record numbers without retry-visible duplicates

### Requirement: Record lifecycle preserves evidence
Record status SHALL be `DRAFT/FILED/ON_HOLD/DISPOSITION_PENDING/DISPOSED`. Filing SHALL require an active category, title, owner/source scope and at least one revision; no API SHALL physically delete a filed or disposed record.

#### Scenario: File empty record
- **WHEN** an operator files a DRAFT record without a revision
- **THEN** the operation returns a business conflict and the record remains DRAFT

### Requirement: Retention cannot be shortened by ordinary edits
The system SHALL derive `retention_until` from filing date and the category snapshot, and ordinary record management SHALL NOT shorten it or change permanent retention.

#### Scenario: Attempt to shorten retention
- **WHEN** a manager edits metadata on a filed record
- **THEN** its retention deadline and permanent flag remain unchanged
