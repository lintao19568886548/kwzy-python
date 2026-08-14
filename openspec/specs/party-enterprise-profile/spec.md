# party-enterprise-profile Specification

## Purpose
TBD - created by archiving change complete-party-enterprise-profile.

## Requirements

### Requirement: Enterprise profile belongs to one organization Party
The system SHALL allow at most one tenant-scoped enterprise profile for an `ORGANIZATION` Party and SHALL reject profile operations for a `PERSON` Party.

#### Scenario: Person profile rejected
- **WHEN** a caller attempts to create an enterprise profile for a PERSON Party
- **THEN** the system rejects the request without creating any profile row

### Requirement: Enterprise profile fields are bounded business facts
The profile SHALL support short name, legal representative, establishment date, registered capital amount and currency, registration status, registration authority, industry code and name, employee-size band, website and business scope. The system SHALL normalize text and enum values, reject unknown fields, validate non-negative capital and valid URLs/dates, and SHALL NOT accept contract, rent, payment or personal identity fields.

#### Scenario: Contract field pollution rejected
- **WHEN** a profile request includes `rent` or `contract_end`
- **THEN** strict request validation rejects the request and no field is persisted

### Requirement: Profile updates use optimistic concurrency
Every enterprise profile SHALL have a monotonically increasing `lock_version`; updates SHALL require the expected current version and stale updates SHALL fail with an explicit conflict without partial writes.

#### Scenario: Stale profile update
- **WHEN** two callers update the same profile with the same expected version
- **THEN** exactly one update succeeds and the other returns a 409 conflict

### Requirement: Completeness is derived and explainable
The API SHALL derive a 0–100 completeness score and missing-dimension codes using these weights: credit code 15, legal representative 10, establishment date 10, registered capital plus currency 10, registration status 5, industry code or name 10, business scope 10, active REGISTERED address 10, active primary contact 10, and active BUSINESS_LICENSE credential 10. Clients SHALL NOT set the score.

#### Scenario: Complete organization profile
- **WHEN** all ten dimensions are present on live Party records
- **THEN** the response reports completeness 100 and an empty missing-dimension list

#### Scenario: Client attempts score override
- **WHEN** a request supplies `completeness_score`
- **THEN** strict validation rejects the request and the derived value remains authoritative

### Requirement: Directory queries use real Party data
Enterprise directory queries SHALL support bounded pagination and filters for keyword, Party lifecycle status, blacklist status, local risk level, registration status, industry and completeness range. Totals and filters SHALL be computed from tenant/park-visible database records.

#### Scenario: Industry and completeness filter
- **WHEN** a visible caller filters by industry and minimum completeness
- **THEN** every returned item satisfies both filters and the total matches the same predicates

### Requirement: External registry status is truthful
The enterprise profile response SHALL include provider state and last verification metadata; without configured and proven external integration, provider state SHALL remain `NOT_CONNECTED` and local edits SHALL NOT claim external verification.

#### Scenario: Local profile edit
- **WHEN** a user saves profile fields without an external provider
- **THEN** provider state remains NOT_CONNECTED and no external verification timestamp is created
