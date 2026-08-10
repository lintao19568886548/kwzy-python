# party-contacts Specification

## Purpose
TBD - created by archiving change design-party-domain. Update Purpose after archive.
## Requirements
### Requirement: Nested contact routes under party
Contact APIs SHALL be nested under /api/v1/parties/{party_id}/contacts and /api/v1/parties/{party_id}/contacts/{contact_id}.

#### Scenario: Contact must match path party
- **WHEN** contact_id belongs to another party
- **THEN** the system returns not found or forbidden without leakage

### Requirement: Multiple contacts with single primary
A Party SHALL support multiple contacts with at most one non-deleted primary. Setting a new primary SHALL clear the previous primary in the same transaction.

#### Scenario: Switch primary
- **WHEN** contact B becomes primary while A was primary
- **THEN** only B remains primary after commit

### Requirement: Primary delete policy
Deleting a primary contact SHALL require a replacement primary or explicit allowance for temporary no-primary.

#### Scenario: Delete primary without replacement rejected
- **WHEN** policy requires a primary and none is provided
- **THEN** the operation fails with CONTACT_PRIMARY_REQUIRED or equivalent

### Requirement: Soft delete contacts
Contact delete SHALL be soft delete by default.

#### Scenario: Soft deleted hidden
- **WHEN** a contact is soft-deleted
- **THEN** default lists exclude it

### Requirement: Sensitive fields masked in logs
Phone and email SHALL be masked in logs and audit details when avoidable.

#### Scenario: Audit masks phone
- **WHEN** contact write is audited
- **THEN** full unmasked phone is not stored in audit detail when masking applies

### Requirement: Optional linked person party
The system SHALL allow optional linked_person_party_id on contacts and SHALL NOT require it in phase one.

#### Scenario: Create without linked person
- **WHEN** linked_person_party_id is omitted
- **THEN** create succeeds

