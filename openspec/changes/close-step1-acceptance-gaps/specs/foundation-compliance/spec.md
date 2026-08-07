## MODIFIED Requirements

### Requirement: Local bootstrap does not embed fixed admin secrets
Local and test bootstrap SHALL seed RBAC structure without embedding a fixed administrator plaintext password in source code.

#### Scenario: Bootstrap creates admin only with external password source in local
- **WHEN** local bootstrap needs to create a missing admin user
- **THEN** the password material comes from environment or fails/skips per secretless-bootstrap rules
- **AND** an existing admin password hash is left unchanged

### Requirement: Successful write audits remain transactional
The system SHALL continue to write Park/Unit success audit records in the same database transaction as the business write.

#### Scenario: Successful park create audits with business commit
- **WHEN** a park is created successfully
- **THEN** an audit_logs row for that create is committed with the business row

## ADDED Requirements

### Requirement: Failed operations are not silently claimed as audited
The system SHALL document that failed operations are not currently persisted in `audit_logs` when the business transaction rolls back, and SHALL treat durable failure auditing as out of scope for this change unless explicitly tasked later.

#### Scenario: Rollback removes in-transaction audit rows
- **WHEN** a business write fails after an in-session audit flush and the transaction rolls back
- **THEN** the audit row is not retained
- **AND** this limitation is accepted as a known gap for a future change

### Requirement: Step1 foundation verification includes migration health
Foundation compliance verification for Step1 SHALL include confirming Alembic unique head alignment for the new-system database when migration ops tasks are executed in apply.

#### Scenario: Post-apply verification expects current equals head
- **WHEN** migration ops verification tasks have been executed in apply
- **THEN** the new-system database current revision matches the unique head
