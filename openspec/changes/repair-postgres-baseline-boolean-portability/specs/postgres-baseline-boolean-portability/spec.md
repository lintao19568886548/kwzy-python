## ADDED Requirements

### Requirement: Boolean updates in baseline migrations are dialect-portable
Baseline Alembic migrations that set Boolean columns SHALL use portable boolean true/false expressions (SQLAlchemy Boolean values or sa.true()/sa.false()) and SHALL NOT use bare integer 1/0 in raw SQL that fails on PostgreSQL.

#### Scenario: Fresh PostgreSQL upgrade reaches head
- **WHEN** alembic upgrade head runs on an empty PostgreSQL 16 test database
- **THEN** the command succeeds and alembic current equals the unique head

#### Scenario: Fresh SQLite upgrade still works
- **WHEN** alembic upgrade head runs on a temporary SQLite database from base
- **THEN** the command succeeds

### Requirement: All-parks semantic preserved
The ADMIN role backfill in revision 9f17fd2e9180 SHALL continue to set all_parks to true for code ADMIN without changing table structure.

#### Scenario: ADMIN all_parks true after upgrade
- **WHEN** upgrade head completes on a database that seeds or later creates ADMIN
- **THEN** the migration itself sets all_parks true for existing ADMIN rows at upgrade time
