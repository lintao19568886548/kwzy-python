# party-api Specification

## Purpose
TBD - created by archiving change design-party-domain. Update Purpose after archive.
## Requirements
### Requirement: Party REST surface under api v1
The API SHALL expose Party operations under /api/v1/parties including list, create, get, patch, archive, and restore. Physical DELETE of Party SHALL NOT be provided.

#### Scenario: Archive endpoint
- **WHEN** POST archive succeeds
- **THEN** status becomes ARCHIVED

### Requirement: Default list excludes archived
List SHALL default to excluding ARCHIVED unless include_archived=true or status=ARCHIVED. Pagination totals SHALL match filters.

#### Scenario: Default omits archived
- **WHEN** list is called without include_archived
- **THEN** ARCHIVED parties are absent from items and total

### Requirement: Risk endpoints and permissions
The API SHALL expose GET /parties/{party_id}/risk-events requiring party:risk_read, POST /parties/{party_id}/blacklist requiring party:risk_manage, and POST /parties/{party_id}/remove-blacklist requiring party:risk_manage. OpenAPI security notes SHALL document these permissions.

#### Scenario: Risk events require risk_read
- **WHEN** caller lacks party:risk_read
- **THEN** risk-events returns PERMISSION_DENIED

### Requirement: Security documents manage_unscoped and risk codes
OpenAPI and security notes SHALL document party:read, party:write, party:manage_unscoped, party:risk_read, and party:risk_manage.

#### Scenario: Permission matrix present in design
- **WHEN** implementers map endpoints
- **THEN** unscoped and risk endpoints map to the dedicated codes

### Requirement: Distinct credit code error codes
The API SHALL distinguish CREDIT_CODE_INVALID, CREDIT_CODE_DUPLICATE, and CREDIT_CODE_ARCHIVED_EXISTS.

#### Scenario: Archived exists
- **WHEN** create hits archived credit_code
- **THEN** CREDIT_CODE_ARCHIVED_EXISTS is returned

### Requirement: Park relation API uses party_role_id
Park relation create APIs SHALL accept party_role_id and SHALL NOT use relation_role string as source of truth.

#### Scenario: Create relation body
- **WHEN** client posts park-relations
- **THEN** body includes park_id and party_role_id

### Requirement: No identity number API in first release
First-release Party APIs SHALL NOT define fields for full identity numbers.

#### Scenario: Schema without id number
- **WHEN** first-release OpenAPI is produced
- **THEN** it does not include id_number fields

### Requirement: No lease bill payment endpoints required
This capability SHALL NOT require Lease, Bill, or Payment endpoints.

#### Scenario: Scope limited
- **WHEN** Party API design is reviewed
- **THEN** required paths remain party resources only

### Requirement: Enterprise profile subresources are strict Party APIs
The API SHALL expose strict `/api/v1/parties/{party_id}` subresources for enterprise profile, related companies, credentials, tags and enterprise risk signals/resolutions. All request schemas SHALL forbid unknown fields and responses SHALL use the standard envelope.

#### Scenario: Unknown relationship field
- **WHEN** a relationship request contains an undeclared permission or tenant field
- **THEN** the API returns 422 and performs no write

### Requirement: Enterprise directory has a bounded query API
The API SHALL expose a paginated enterprise directory query with server-enforced page bounds, filter enums and sort allow-list. Unbounded export or arbitrary sort expressions SHALL NOT be accepted.

#### Scenario: Excessive page size
- **WHEN** a client asks for more than the configured maximum page size
- **THEN** validation rejects or caps it according to the documented contract without an unbounded query

### Requirement: Child identifiers are checked against path Party
Every profile-child route SHALL validate that the child belongs to the tenant and `party_id` in the path; a valid child id under a foreign Party path SHALL return not found without leakage.

#### Scenario: Foreign credential path
- **WHEN** a caller places Party B's credential id under Party A's path
- **THEN** the API returns not found and does not expose which Party owns it

### Requirement: API does not expose personal or raw credential identifiers
OpenAPI schemas SHALL forbid personal identity-number fields and SHALL not define raw organization credential identifiers in responses. Credential write descriptions SHALL document one-way reduction and sensitive logging boundaries.

#### Scenario: OpenAPI inspection
- **WHEN** the runtime and YAML contracts are validated
- **THEN** no response schema contains raw credential or personal identity number fields

### Requirement: API method sets are exact
Runtime routes and the checked-in OpenAPI YAML SHALL have exact method sets for every new endpoint, and no physical DELETE SHALL exist for enterprise relationships, credentials, tags or risk signals.

#### Scenario: Method contract
- **WHEN** runtime routes are compared with YAML
- **THEN** the enterprise endpoint method sets match exactly and lifecycle actions use explicit POST/PATCH operations

