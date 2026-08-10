## ADDED Requirements

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
