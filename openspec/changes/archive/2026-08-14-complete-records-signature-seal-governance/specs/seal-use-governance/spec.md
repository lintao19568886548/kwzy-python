## ADDED Requirements

### Requirement: Use applications bind exact immutable evidence
A seal-use application SHALL reference one ACTIVE seal and one filed record revision checksum, capture purpose, copy count, requested time and applicant, and SHALL not accept a mutable attachment id without a record revision.

#### Scenario: Revision superseded after approval
- **WHEN** execution targets a checksum different from the approved revision
- **THEN** execution is rejected and a new application is required

### Requirement: Platform approval is authoritative
Submitting a use application SHALL create or reuse exactly one native platform approval. `APPROVED/REJECTED/WITHDRAWN` execution eligibility SHALL be derived from that approval, not a client field or JWT claim.

#### Scenario: Forged approved field
- **WHEN** a client sends an approved-looking field without an approved workflow
- **THEN** the request is rejected and no usage receipt exists

### Requirement: Execution enforces custody and separation of duties
Only the current custodian with `seal:execute` SHALL execute an approved application. High-risk seal kinds SHALL require applicant, final approver and executor to be distinct unless an audited emergency override permission and reason are present.

#### Scenario: Applicant executes contract seal
- **WHEN** the applicant attempts to execute an approved CONTRACT seal use
- **THEN** the operation is denied by separation-of-duty policy

### Requirement: Usage receipts are immutable and idempotent
Execution SHALL append one immutable receipt containing application, seal, revision checksum, copy count, executor, time and optional same-scope evidence attachment. Repeating the same idempotency key/payload returns the same receipt; changed payload conflicts.

#### Scenario: Repeat execution
- **WHEN** the same authorized command is retried after a timeout
- **THEN** one receipt exists and no duplicate copy count or audit event is created
