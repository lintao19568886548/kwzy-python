## ADDED Requirements

### Requirement: New Alembic revision for lease tables
Implementation SHALL add a single new Alembic revision creating lease_contracts, lease_contract_units, and lease_terms with down_revision equal to the Party head at apply time, keeping a unique head.

#### Scenario: Upgrade on PostgreSQL 16
- **WHEN** alembic upgrade head runs on empty PostgreSQL 16
- **THEN** lease tables exist and alembic current equals heads

#### Scenario: Downgrade removes lease tables
- **WHEN** alembic downgrade -1 runs after lease revision
- **THEN** lease tables are dropped without breaking Party tables
