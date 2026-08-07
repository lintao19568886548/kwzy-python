# step1-db-migration-ops Specification

## Purpose
TBD - created by archiving change close-step1-acceptance-gaps. Update Purpose after archive.
## Requirements
### Requirement: New-system-only database target
The system SHALL perform Step1 migration operations only against the new-system database configured by `DATABASE_URL`, and SHALL refuse operations when the URL points at the legacy Java system database.

#### Scenario: Accept local SQLite path
- **WHEN** `DATABASE_URL` points to the new-system SQLite file under `apps/api` (for example `sqlite+pysqlite:///./kwzy_step1.db`)
- **THEN** migration verification is allowed to proceed

#### Scenario: Reject legacy database
- **WHEN** `DATABASE_URL` matches a configured legacy host/database pattern or is known not to be the new-system store
- **THEN** migration verification SHALL fail closed without applying changes

### Requirement: Timestamped backup before upgrade
Before applying `alembic upgrade head` to the Step1 SQLite database, the operator process SHALL create a same-directory file backup whose name includes a timestamp.

#### Scenario: Backup file created
- **WHEN** a pre-upgrade backup step runs against `kwzy_step1.db`
- **THEN** a file such as `kwzy_step1.backup.YYYYMMDD-HHMMSS.db` exists beside the original database

### Requirement: Upgrade to unique head
After a successful upgrade, `alembic current` SHALL equal the single Alembic head revision.

#### Scenario: Current matches head
- **WHEN** upgrade and verification complete successfully
- **THEN** the reported current revision equals the unique head (currently `8c2f4aa10b7d`) and no multiple heads exist

### Requirement: Preserve existing business rows
Upgrade SHALL NOT drop or empty existing Tenant, User, Park, or Unit business data present before upgrade.

#### Scenario: Counts preserved
- **WHEN** row counts for tenants, users, parks, and units are recorded before upgrade
- **THEN** post-upgrade counts are greater than or equal to the pre-upgrade counts for those tables

### Requirement: RBAC and audit tables exist after upgrade
After upgrade to head, the database SHALL contain `permissions`, `role_permissions`, `user_roles`, `role_park_scopes`, and `audit_logs` tables.

#### Scenario: Tables present
- **WHEN** post-upgrade schema inspection runs
- **THEN** each of those tables is present

### Requirement: Full test suite after upgrade
After a successful upgrade, the full isolated pytest suite for `apps/api` SHALL be executed and pass.

#### Scenario: Pytest green
- **WHEN** post-upgrade verification runs the full suite
- **THEN** the suite exits successfully with zero failures

### Requirement: Documented rollback
The change tasks SHALL document file-level restore from the timestamped backup as the primary rollback method and SHALL NOT require writing to the legacy Java database.

#### Scenario: Restore from backup
- **WHEN** upgrade fails or is rejected after backup
- **THEN** operators can restore by replacing `kwzy_step1.db` with the timestamped backup file

