# party-enterprise-credentials Specification

## Purpose
TBD - created by archiving change complete-party-enterprise-profile.

## Requirements

### Requirement: Credentials are organization-only attachment-backed metadata
Credentials SHALL be available only for `ORGANIZATION` Parties and SHALL use one of `BUSINESS_LICENSE`, `TAX_REGISTRATION`, `ORGANIZATION_CODE`, `INDUSTRY_LICENSE` or `OTHER`. Every active credential SHALL reference an ACTIVE attachment visible in the same tenant and compatible park scope.

#### Scenario: Cross-tenant attachment id
- **WHEN** a credential references another tenant's attachment
- **THEN** the system returns not found and persists no credential

#### Scenario: Person credential rejected
- **WHEN** a caller creates a credential for a PERSON Party
- **THEN** the system rejects it and does not accept identity document content

### Requirement: Raw credential identifiers are not persisted or returned
If an organization credential identifier is supplied, the system SHALL normalize it in memory, persist only a SHA-256 fingerprint and masked suffix, and SHALL exclude the raw value from responses, audit details, ordinary logs, errors and migration reports. Personal identity-number field names SHALL be rejected.

#### Scenario: Credential response masking
- **WHEN** a credential is created with an organization identifier
- **THEN** the response contains only a masked identifier and never the raw value

#### Scenario: Personal id parameter pollution
- **WHEN** a request includes `id_number` or equivalent personal identity field
- **THEN** strict validation rejects the entire request

### Requirement: Credential validity is explicit
Credentials SHALL record issue and expiry dates, issuer, status `ACTIVE/EXPIRED/REVOKED/ARCHIVED`, and optimistic lock version. The derived effective status SHALL treat a passed expiry date as expired even before a maintenance job runs.

#### Scenario: Expired credential read
- **WHEN** an ACTIVE credential has an expiry date before today
- **THEN** the read model reports it as expired and it does not satisfy profile completeness

### Requirement: Verification does not fabricate provider completion
Credential verification states SHALL be `UNVERIFIED`, `LOCALLY_REVIEWED`, `EXTERNALLY_VERIFIED` or `REJECTED`. Local APIs MAY set only `LOCALLY_REVIEWED` or `REJECTED` with reviewer, reason and time; `EXTERNALLY_VERIFIED` SHALL require a separately configured provider adapter and immutable provider evidence.

#### Scenario: Local external verification spoof
- **WHEN** a local management request tries to set EXTERNALLY_VERIFIED
- **THEN** the system rejects the transition and provider state remains unchanged

### Requirement: Credential metadata has dedicated permissions
Credential list/detail SHALL require `party:credential_read`; create, update, archive and local review SHALL require `party:credential_manage`. Ordinary `party:read` SHALL expose at most a credential count and expiring indicator.

#### Scenario: Ordinary Party reader
- **WHEN** a user has party:read but lacks party:credential_read
- **THEN** enterprise detail excludes credential identifiers, attachment ids and issuer metadata
