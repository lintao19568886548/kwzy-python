## ADDED Requirements

### Requirement: PostgreSQL 16 is production dialect
The production target database for the new system Party feature SHALL be PostgreSQL 16. MySQL and MariaDB SHALL NOT be the current production target.

#### Scenario: Production configuration uses PostgreSQL
- **WHEN** production DATABASE_URL is documented for Party
- **THEN** it targets PostgreSQL 16 and not MySQL or MariaDB

### Requirement: SQLite is non-production only
SQLite SHALL be used only for local fast development and unit tests. SQLite SHALL NOT be the production database and SHALL NOT be the sole environment for validating database constraints.

#### Scenario: SQLite pass is insufficient for production constraints
- **WHEN** only SQLite tests pass for unique indexes or foreign keys
- **THEN** Party implementation is not considered production-ready for those constraints

### Requirement: PostgreSQL is source of truth on dialect differences
When SQLite and PostgreSQL behavior differ, the system SHALL treat PostgreSQL 16 as authoritative.

#### Scenario: Conflict resolved toward PostgreSQL
- **WHEN** a constraint behaves differently on SQLite and PostgreSQL
- **THEN** design and implementation follow PostgreSQL 16

### Requirement: Alembic authority is PostgreSQL
Alembic migrations for Party SHALL be authored with PostgreSQL 16 as the authoritative dialect while keeping domain and ORM mapping database-agnostic where practical.

#### Scenario: Migration reviewed for PostgreSQL
- **WHEN** Party migrations are implemented
- **THEN** partial unique indexes and types are correct for PostgreSQL 16

### Requirement: PostgreSQL integration tests are mandatory for Party implementation
Party implementation SHALL include a PostgreSQL 16 integration test environment that at least validates Alembic upgrade from base to head, downgrade then upgrade, tenant isolation, non-null credit_code uniqueness, ACTIVE park relation partial unique index, foreign keys, concurrent duplicate Party creates, concurrent duplicate active park relations, soft delete and restore, and transactional auditing including risk events.

#### Scenario: Integration suite covers concurrent relation uniqueness
- **WHEN** PostgreSQL integration tests run
- **THEN** concurrent active park relation creates are covered

### Requirement: CI includes SQLite and PostgreSQL tracks
Future CI SHALL include a fast SQLite test job and a PostgreSQL 16 integration test job for Party-related work.

#### Scenario: Two CI tracks planned
- **WHEN** Party implement change is planned
- **THEN** both SQLite and PostgreSQL test tracks are listed

### Requirement: Connection secrets stay out of source
PostgreSQL connection strings SHALL be supplied only via environment variables. Source code, design docs, and test outputs SHALL NOT contain real database passwords.

#### Scenario: No password in repository docs
- **WHEN** repository documentation is reviewed
- **THEN** no real production database password is present
