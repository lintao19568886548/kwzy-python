## ADDED Requirements

### Requirement: Mounted strict engagement APIs
The system SHALL mount versioned staff and tenant-principal engagement route groups with strict request schemas, bounded paging and bulk sizes, stable error envelopes, and matching runtime and checked-in OpenAPI contracts.

#### Scenario: Unknown or duplicate input
- **WHEN** a caller sends an unknown body field or repeats a singleton query parameter
- **THEN** validation fails before database work and no partial mutation remains

### Requirement: Database-derived tenant, park, Party, and permission scope
The system SHALL derive permissions and tenant-principal Party/park grants from authenticated database state on every request and SHALL return non-disclosing not found for foreign resource identifiers.

#### Scenario: Forged authorization claims
- **WHEN** a caller supplies client-controlled role, Party, park, or permission headers
- **THEN** those values grant no authority and inaccessible engagement data is not disclosed

### Requirement: Idempotent and concurrency-safe commands
Every engagement mutation SHALL bind an idempotency key to a canonical request fingerprint and SHALL enforce an expected version or database lock for state, capacity, audience, and delivery transitions.

#### Scenario: Same key with different command
- **WHEN** an idempotency key is reused with a different payload or target version
- **THEN** the system returns conflict and creates no additional case, registration, event, publication, or delivery

### Requirement: Safe content, links, audit, and sensitive projections
The system SHALL sanitize and bound rich content, validate external link schemes and hosts without synchronously fetching caller-controlled URLs, minimize contact and profile fields, and audit privileged transitions with actor and request correlation.

#### Scenario: Unsafe source link
- **WHEN** a policy or announcement includes a local, private-network, script, data, or malformed URL
- **THEN** the request is rejected and the URL is absent from persistence, logs, audit, and responses
