## ADDED Requirements

### Requirement: Transactional audit records
The system SHALL write an audit record in the same database transaction as each Park and Unit create, update, status-change, and delete operation. Audit records SHALL include tenant_id, user_id, request_id, action, resource type/id, optional park_id, and a non-sensitive detail summary.

#### Scenario: Successful Park update
- **WHEN** a Park update commits
- **THEN** the corresponding audit record is committed with the same tenant and resource ID

#### Scenario: Failed business write
- **WHEN** a Park or Unit write fails before commit
- **THEN** no audit record for that failed action is committed

### Requirement: Safe production configuration
The system MUST reject production startup when JWT_SECRET uses the documented default or CORS_ORIGINS is unrestricted.

#### Scenario: Default JWT secret in production
- **WHEN** Settings loads with APP_ENV=production and JWT_SECRET=change-me-in-production
- **THEN** configuration validation fails before the application starts

#### Scenario: Explicit production configuration
- **WHEN** production uses a non-default JWT secret and explicit allowed origins
- **THEN** Settings validation succeeds

### Requirement: Foundation verification suite
The project SHALL maintain automated tests for tenant login ambiguity, RBAC permission resolution, production authentication, invalid statuses, soft deletion, uniform error envelopes, request IDs, and audit records, while preserving existing isolation tests.

#### Scenario: Full foundation test run
- **WHEN** the project test suite runs against the isolated test database
- **THEN** all original Step1 tests and all foundation-hardening tests pass without external services

### Requirement: Documentation reflects runtime semantics
The Step1 implementation documentation SHALL state that empty park_ids means no park access unless `*` or platform admin is explicit, and SHALL distinguish implemented APIs from planned stubs.

#### Scenario: Completion report review
- **WHEN** a developer reads the Step1 completion report
- **THEN** the documented data-scope behavior matches TenantContext and the report identifies non-mounted stub modules
