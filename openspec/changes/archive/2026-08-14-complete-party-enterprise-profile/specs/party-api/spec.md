## ADDED Requirements

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
