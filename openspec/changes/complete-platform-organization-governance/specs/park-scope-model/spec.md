## ADDED Requirements

### Requirement: Region membership does not grant park scope
The system MUST keep region-to-park governance membership independent from user and role park grants; hierarchy membership SHALL NOT expand `TenantContext` park access.

#### Scenario: Region manager without park grant
- **WHEN** a user is assigned a position associated with a region or one of its parks but lacks explicit role/direct park scope
- **THEN** the user cannot read or mutate that park's governed resources

### Requirement: Park assignment commands enforce explicit scope
The system SHALL require an organization governance writer to have explicit access to every park referenced by an assignment or reassignment command.

#### Scenario: Cross-scope reassignment denied
- **WHEN** a writer with LIST scope for park A attempts to reassign park B
- **THEN** the system returns park-scope denial or a non-enumerating not-found response and leaves history unchanged
