# party-addresses Specification

## Purpose

Define Party address storage, ownership, privacy, lifecycle, and audit requirements.

## Requirements

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

ORGANIZATION parties SHALL be allowed to use address CRUD in the first release when authorized. PERSON parties SHALL have all address access disabled in v1 until KMS, field encryption, data classification, and dedicated PII permissions exist in a separate change. ORGANIZATION address behavior SHALL remain unchanged by the PERSON lockdown.

#### Scenario: Person address write forbidden

- **WHEN** a client creates an address for a PERSON party in first release
- **THEN** the API rejects the write with PERSON_ADDRESS_FORBIDDEN

### Requirement: PERSON address full deny in v1 (temporary security boundary)

Until an independent KMS/PII change lands, Party v1 SHALL refuse PERSON address create, update, delete, list, and detail reads. Application service layer SHALL enforce the rule (not router-only). No temporary party:pii:* permission codes SHALL be introduced in this change. Party list and Party detail responses SHALL NOT embed PERSON addresses, address counts, or address summaries.

#### Scenario: Person address list forbidden

- **WHEN** a client lists addresses for a PERSON party
- **THEN** the API returns 403 with code PERSON_ADDRESS_FORBIDDEN and empty data payload without address fields

#### Scenario: Person address update and delete forbidden

- **WHEN** a client updates or deletes an address under a PERSON party
- **THEN** the API returns 403 with code PERSON_ADDRESS_FORBIDDEN

#### Scenario: Preexisting PERSON address rows not leaked

- **WHEN** party_addresses already contains rows for a PERSON party (e.g. manual insert or future migration)
- **THEN** list/detail/read APIs still return 403 and do not return street, detail, or any address payload

#### Scenario: Organization addresses unaffected

- **WHEN** an authorized client performs address CRUD for an ORGANIZATION party
- **THEN** create, list, update, and soft-delete continue to work as approved

### Requirement: Address writes audited without verbose logs

Successful ORGANIZATION address writes SHALL be audited. Ordinary business logs, audit detail_json, exception messages, and test assertions SHALL NOT include full address field dumps (street/detail lines). PERSON address denials SHALL NOT log or audit full address content.

#### Scenario: Audit without log dump

- **WHEN** an ORGANIZATION address is created
- **THEN** an audit record exists and structured logs do not print full street/detail lines
