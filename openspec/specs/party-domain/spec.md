# party-domain Specification

## Purpose
TBD - created by archiving change design-party-domain. Update Purpose after archive.
## Requirements
### Requirement: Party is tenant-scoped master data without single park ownership
The system SHALL model Party as tenant-scoped master data without a single required owning park_id on the master row.

#### Scenario: Create party without park_id column
- **WHEN** a Party is created
- **THEN** it is stored with tenant_id from context and park associations are handled only via party_park_relations when present

### Requirement: Party type is legal form only
Party party_type SHALL be only ORGANIZATION or PERSON and SHALL NOT encode business roles.

#### Scenario: Organization type
- **WHEN** party_type is ORGANIZATION
- **THEN** the Party is stored as ORGANIZATION

#### Scenario: Person type
- **WHEN** party_type is PERSON
- **THEN** the Party is stored as PERSON

### Requirement: Lifecycle status values
Party lifecycle status SHALL be one of ACTIVE, INACTIVE, or ARCHIVED.

#### Scenario: Reject unknown lifecycle status
- **WHEN** status is set outside the allowed set
- **THEN** the system rejects the change

### Requirement: Archive is soft delete
Archiving SHALL set status to ARCHIVED and SHALL NOT physically delete the Party.

#### Scenario: Archive action
- **WHEN** archive succeeds
- **THEN** status is ARCHIVED and default lists exclude it

### Requirement: Restore rechecks credit code uniqueness
Restore from ARCHIVED SHALL re-validate credit_code uniqueness in the tenant before leaving archived status.

#### Scenario: Restore blocked by duplicate
- **WHEN** restore would violate credit_code uniqueness
- **THEN** restore fails with a credit-code conflict

### Requirement: Credit code optional but unique when present
The system SHALL allow empty credit_code. When present, the system SHALL normalize with trim and uppercase and SHALL enforce uniqueness within tenant_id including ARCHIVED rows, without using park_id in the unique key.

#### Scenario: Duplicate rejected
- **WHEN** another Party in the tenant already has the normalized credit_code
- **THEN** create or update fails with a duplicate error

#### Scenario: Archived code blocks create
- **WHEN** an ARCHIVED Party holds the credit_code
- **THEN** create fails with archived-exists conflict and prompts restore semantics

#### Scenario: Cross-tenant same code allowed
- **WHEN** two SaaS tenants use the same credit_code
- **THEN** both may succeed

### Requirement: Credit code format validation
Non-empty credit_code SHALL be validated against unified social credit code format rules.

#### Scenario: Invalid format
- **WHEN** format validation fails
- **THEN** the system returns CREDIT_CODE_INVALID or equivalent

### Requirement: First release excludes person identity number storage
The first Party release SHALL NOT accept full identity numbers via API and SHALL NOT create database columns for plaintext id numbers or id_number_ciphertext, id_number_hash, or id_number_masked. Logs, audits, and errors SHALL NOT record identity numbers. Future identity storage SHALL require a separate PII security OpenSpec change after KMS and encryption capabilities exist.

#### Scenario: No identity fields in first schema
- **WHEN** the first Party migration is designed
- **THEN** it does not include identity number related columns

#### Scenario: API rejects identity payloads if sent
- **WHEN** a client sends a full identity number field in first-release Party APIs
- **THEN** the field is not persisted as identity storage (ignored or validation error per implementation choice documented at implement time)

### Requirement: No lease contract fields on Party
Party SHALL NOT store contract_start, contract_end, rent, or increase fields.

#### Scenario: Mapping excludes contract columns
- **WHEN** field mapping is reviewed
- **THEN** contract fields belong to Lease design, not Party

### Requirement: Tenant id stamped from context
Party writes SHALL stamp tenant_id from context and MUST NOT trust client tenant_id.

#### Scenario: Spoofed tenant ignored
- **WHEN** payload includes another tenant_id
- **THEN** stored tenant_id equals context tenant_id

