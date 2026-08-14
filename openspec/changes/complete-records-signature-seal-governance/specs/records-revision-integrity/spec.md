## ADDED Requirements

### Requirement: Revisions bind exact scoped attachments
Each revision SHALL reference an ACTIVE attachment in the same tenant and compatible park/business scope. The service SHALL derive SHA-256, size and MIME from stored bytes rather than trust client checksum input.

#### Scenario: Cross-tenant attachment reference
- **WHEN** a revision command references another tenant's attachment id
- **THEN** the API returns 404 and creates no revision

### Requirement: Filed revisions are immutable
Revision version numbers SHALL be monotonic per record and unique under concurrency. A filed record SHALL NOT allow mutation or removal of an existing revision; an authorized correction creates a new superseding revision before re-filing rules permit it.

#### Scenario: Concurrent revision append
- **WHEN** two operators append against the same expected record version
- **THEN** exactly one succeeds and the other receives a version conflict

### Requirement: Integrity verification is repeatable
Authorized verification SHALL re-read stored bytes, recompute SHA-256 and append an integrity event with `MATCH/MISMATCH/UNAVAILABLE` without returning object keys, credentials or file content.

#### Scenario: Stored bytes differ
- **WHEN** verification computes a checksum different from the filed revision
- **THEN** a MISMATCH event is appended and the record is placed on hold

### Requirement: Responses expose safe evidence only
Record and revision responses SHALL expose bounded metadata, checksum, provider truth and integrity status, and SHALL NOT expose storage object keys, unrestricted URLs, raw signature material or file bodies.

#### Scenario: Ordinary record detail
- **WHEN** a records reader views a filed record
- **THEN** the response omits object storage keys and credentials
