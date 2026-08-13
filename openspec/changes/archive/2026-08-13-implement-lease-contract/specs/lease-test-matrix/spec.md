## ADDED Requirements

### Requirement: Automated test matrix
Implementation SHALL provide domain, application/API, repository, permission, tenant isolation, park scope, occupancy conflict, used_area projection, audit, SQLite, and PostgreSQL 16 tests for lease.

#### Scenario: PostgreSQL marker tests
- **WHEN** pytest -m pg runs with TEST_DATABASE_URL
- **THEN** lease-related PG cases pass including migration head checks if applicable
