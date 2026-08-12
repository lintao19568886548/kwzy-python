## ADDED Requirements

### Requirement: Identity admin writes use foundation envelopes and audit
Identity user/role/menu/park-scope administration successful writes SHALL use the standard success envelope and SHALL create audit records in the same transaction as the business write when audit infrastructure is available. Failed writes SHALL use the standard error envelope and MUST NOT commit partial business changes.

#### Scenario: User update success envelope
- **WHEN** an authorized admin successfully updates a user
- **THEN** the response uses the standard success envelope and an audit record is committed with the business change

#### Scenario: User update validation failure
- **WHEN** user update payload fails validation
- **THEN** the system returns a structured error envelope without committing user changes
