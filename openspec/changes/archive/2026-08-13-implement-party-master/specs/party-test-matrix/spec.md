## ADDED Requirements

### Requirement: SQLite fast test track
Implementation SHALL provide automated tests on SQLite for domain rules and API happy paths for rapid feedback. SQLite SHALL NOT be treated as sufficient proof of production dialect constraints.

#### Scenario: Fast pytest on SQLite
- **WHEN** default unit/api tests execute
- **THEN** they pass on isolated SQLite

### Requirement: PostgreSQL 16 integration track
Implementation SHALL provide PostgreSQL 16 integration tests covering connection health, alembic base to head, head to down revision to head, tenant isolation, credit_code uniqueness, active park relation partial unique index, concurrent duplicate party and relation creates, foreign keys, soft delete and restore, transactional risk events with audit, and address primary uniqueness where applicable.

#### Scenario: Integration requires env URL
- **WHEN** PostgreSQL integration tests are selected
- **THEN** they read TEST_DATABASE_URL or POSTGRES_TEST_URL style env vars and fail or skip clearly if unset

### Requirement: Explicit PostgreSQL gate tasks
Tasks SHALL include explicit gates: verify PostgreSQL 16 connection; alembic base to head; head to down to head; run PG integration suite; verify partial unique indexes; verify concurrent unique conflicts; verify transactions and foreign keys; verify tenant isolation.

#### Scenario: Gate tasks present in plan
- **WHEN** implement-party-master tasks are reviewed
- **THEN** the PostgreSQL gate tasks are listed before Complete

### Requirement: Visibility permission and OpenAPI contract tests
Tests SHALL cover manage_unscoped, park scope intersection, risk permission separation, credit archived-exists, Party schema without master park_id, and OpenAPI strict validation after sync.

#### Scenario: Contract test blocks master park_id
- **WHEN** schema contract tests run
- **THEN** Party master park_id ownership field is rejected

### Requirement: Full regression
Completion SHALL require full existing Step1 pytest suite plus Party tests to pass on the intended tracks.

#### Scenario: Full suite green
- **WHEN** complete tests run after delivery
- **THEN** all required tracks pass
