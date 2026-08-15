# Supplier Governance

## ADDED Requirements

### Requirement: Tenant supplier identity
The system SHALL bind each supply supplier to an organization Party with supplier role in the same tenant and SHALL reject cross-tenant references.

#### Scenario: Create an eligible supplier
- **WHEN** an authorized operator selects a same-tenant organization Party and supplies a unique supplier code
- **THEN** the system creates an auditable supplier without duplicating the Party identity

#### Scenario: Hide a foreign supplier
- **WHEN** a caller references a supplier outside the caller tenant or park scope
- **THEN** the system returns not found and does not reveal its existence

### Requirement: Scope and qualification eligibility
The system SHALL permit procurement or outsourcing selection only when the supplier is active, scoped to the park, and has every required non-expired qualification.

#### Scenario: Reject expired qualification
- **WHEN** a supplier qualification required for an order is expired
- **THEN** submission is rejected with a stable business conflict and no approval is created

### Requirement: Protected qualification credentials
The system SHALL store only a masked display value and keyed fingerprint for qualification credentials and SHALL append supplier evaluations rather than overwrite them.

#### Scenario: Read a qualification
- **WHEN** an authorized caller reads qualification evidence
- **THEN** the API returns the masked value and never returns the raw credential
