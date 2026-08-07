## MODIFIED Requirements

### Requirement: Transactional audit records
The system SHALL write an audit record in the same database transaction as each Park and Unit create, update, status-change, and delete operation that succeeds. Audit records SHALL include tenant_id, user_id, request_id, action, resource type/id, optional park_id, and a non-sensitive detail summary.

#### Scenario: Successful Park update
- **WHEN** a Park update commits
- **THEN** the corresponding audit record is committed with the same tenant and resource ID

#### Scenario: Successful park create audits with business commit
- **WHEN** a park is created successfully
- **THEN** an audit_logs row for that create is committed with the business row

#### Scenario: Failed business write
- **WHEN** a Park or Unit write fails before commit
- **THEN** no audit record for that failed action is committed

### Requirement: Documentation reflects runtime semantics
The Step1 implementation documentation SHALL state that empty park_ids means no park access unless an explicit all-parks grant sets park scope mode ALL, that action permission `*` does not grant all-park access, and SHALL distinguish implemented APIs from planned stubs.

#### Scenario: Completion report review
- **WHEN** a developer reads the Step1 completion or acceptance documentation
- **THEN** the documented data-scope behavior matches TenantContext park_scope_mode semantics and the report identifies non-mounted stub modules

### Requirement: Foundation verification suite
The project SHALL maintain automated tests for tenant login ambiguity, RBAC permission resolution, park-scope orthogonality to `*`, production authentication, invalid statuses, soft deletion, uniform error envelopes, request IDs, audit records, layering guards, and OpenAPI contract checks, while preserving existing isolation tests.

#### Scenario: Full foundation test run
- **WHEN** the project test suite runs against the isolated test database
- **THEN** all Step1 and foundation tests pass without external services

## ADDED Requirements

### Requirement: Local bootstrap does not embed fixed admin secrets
Local and test bootstrap SHALL seed RBAC structure without embedding a fixed administrator plaintext password in source code.

#### Scenario: Bootstrap creates admin only with external password source in local
- **WHEN** local bootstrap needs to create a missing admin user
- **THEN** the password material comes from environment or fails/skips per secretless-bootstrap rules
- **AND** an existing admin password hash is left unchanged

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
