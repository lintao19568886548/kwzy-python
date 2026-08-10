## ADDED Requirements

### Requirement: Addresses live in party_addresses table
Party postal and registered locations SHALL be stored in party_addresses, not as a single ambiguous address column on the Party master.

#### Scenario: Master has no address fact column
- **WHEN** Party master schema is reviewed
- **THEN** it does not use a free-form master address field as the source of truth for locations

### Requirement: Address types and primary rule
address_type SHALL be one of REGISTERED, OFFICE, MAILING, BILLING, or OTHER. At most one active primary address per party and address_type SHALL exist.

#### Scenario: Second primary same type rejected
- **WHEN** a second primary REGISTERED address is created for the same party
- **THEN** the operation fails with a primary conflict

### Requirement: Nested address routes and ownership
Address APIs SHALL be nested under /api/v1/parties/{party_id}/addresses and SHALL enforce that address_id belongs to the path party_id and tenant.

#### Scenario: Cross-party address access denied
- **WHEN** address_id belongs to another party
- **THEN** the system returns not found or forbidden without leakage

### Requirement: Soft delete and archive retention
Address delete SHALL be soft delete. Archiving a Party SHALL NOT physically delete address rows.

#### Scenario: Soft deleted excluded from default list
- **WHEN** an address is soft-deleted
- **THEN** default list excludes it

### Requirement: Organization vs person address policy
ORGANIZATION parties SHALL be allowed to use address CRUD in the first release when authorized. PERSON address writes SHALL be disabled in the first release until personal PII access controls exist. PERSON detailed addresses SHALL NOT be exposed without proper authorization.

#### Scenario: Person address write forbidden
- **WHEN** a client creates an address for a PERSON party in first release
- **THEN** the API rejects the write

### Requirement: Address writes audited without verbose logs
Successful address writes SHALL be audited. Ordinary business logs SHALL NOT include full address field dumps.

#### Scenario: Audit without log dump
- **WHEN** an address is created
- **THEN** an audit record exists and structured logs do not print full street/detail lines
