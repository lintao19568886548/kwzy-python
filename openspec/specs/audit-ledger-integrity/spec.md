# audit-ledger-integrity Specification

## Purpose
TBD - created by archiving change complete-platform-approval-audit-center. Update Purpose after archive.
## Requirements
### Requirement: Append-only deterministic audit ledger
Every newly recorded audit event SHALL receive a tenant-local sequence, previous hash and deterministic record hash calculated from canonical non-sensitive fields; application APIs SHALL expose no update/delete command for audit rows.

#### Scenario: Consecutive records verify
- **WHEN** two successful business writes are audited for the same tenant
- **THEN** the second record references the first hash and verification reports both records intact

#### Scenario: Concurrent audit writes serialize safely
- **WHEN** multiple transactions append audit records for one tenant concurrently
- **THEN** committed sequence numbers and hashes form one unbroken order without duplicates

### Requirement: Safe canonical audit payload
Audit recording SHALL allow only JSON-compatible bounded detail, SHALL reject or redact secret/credential fields, SHALL mask registered PII, and SHALL enforce a serialized size limit before persistence.

#### Scenario: Secret key rejected
- **WHEN** audit detail contains a password, token, authorization header or equivalent blocked key
- **THEN** the recorder rejects or removes that value before persistence and no plaintext secret reaches the ledger

#### Scenario: Phone value masked
- **WHEN** an allow-listed phone summary is audited
- **THEN** the canonical detail contains only the deterministic masked form

### Requirement: Explicit legacy integrity state
Rows created before hash-ledger activation SHALL remain readable as `LEGACY_UNVERIFIED`; migration SHALL NOT invent a historical chain or report those rows as verified.

#### Scenario: Mixed history verification
- **WHEN** a query spans legacy rows and new chained rows
- **THEN** each legacy row is marked unverified while valid new rows are marked verified

#### Scenario: Tampered hash detected
- **WHEN** verification encounters a stored hash or previous-hash mismatch
- **THEN** the affected row and subsequent chain are reported failed without rewriting evidence
