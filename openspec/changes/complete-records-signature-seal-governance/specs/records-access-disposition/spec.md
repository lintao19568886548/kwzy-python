## ADDED Requirements

### Requirement: Legal holds are append-only and block disposition
Authorized users SHALL place and release reasoned legal holds with immutable events. An active hold SHALL set record status `ON_HOLD` and block disposition regardless of elapsed retention.

#### Scenario: Dispose held record
- **WHEN** disposition is attempted while any legal hold is active
- **THEN** it is rejected and all evidence remains unchanged

### Requirement: Access and borrow require governed approval
An access request SHALL capture requester, purpose, mode `VIEW/BORROW`, requested expiry and exact record. Approval SHALL come from the platform approval authority; approved borrow can be checked out once and must be returned or expired explicitly.

#### Scenario: Requester approves own high-sensitivity borrow
- **WHEN** a requester is also the only approving actor for a RESTRICTED record
- **THEN** self-approval is rejected and no checkout is created

### Requirement: Disposition requires retention expiry and two-person confirmation
Disposition SHALL require expired non-permanent retention, no active hold/borrow/signature/seal dependency, an approved platform application and two distinct authorized confirmations. Applicant and both confirmers SHALL satisfy separation-of-duty policy.

#### Scenario: Same confirmer twice
- **WHEN** one user submits both destruction confirmations
- **THEN** the second confirmation is rejected and the record is not disposed

### Requirement: Disposition is metadata-only in local acceptance
Successful local disposition SHALL mark the record and revisions DISPOSED, append a checksum manifest and audit/event facts, but SHALL NOT physically delete object storage. Production deletion requires separate authorization and provider evidence.

#### Scenario: Local disposition completes
- **WHEN** all local synthetic gates pass
- **THEN** storage content still exists and the response identifies deletion as NOT_EXECUTED
