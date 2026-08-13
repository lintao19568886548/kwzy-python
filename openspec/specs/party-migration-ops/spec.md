# party-migration-ops Specification

## Purpose

Define Party schema migration and PostgreSQL 16 verification requirements.

## Requirements

### Requirement: Alembic migration for Party tables

Implementation SHALL add Alembic migration(s) creating parties, party_roles, party_park_relations, party_contacts, party_risk_events, and party_addresses aligned with the approved DDL draft and PostgreSQL 16 as the authoritative dialect.

#### Scenario: Upgrade creates party tables including addresses

- **WHEN** alembic upgrade head runs on PostgreSQL 16
- **THEN** Party-related tables including party_addresses exist

### Requirement: Partial unique indexes on PostgreSQL

Migration SHALL create partial unique indexes for active park relations and for active primary addresses per type on PostgreSQL 16.

#### Scenario: Duplicate active relation fails at database

- **WHEN** two active relations with the same business key are inserted
- **THEN** the second insert is rejected by the database

### Requirement: Preferred test database via Docker Compose

The preferred local and CI approach SHALL be a disposable PostgreSQL 16 container via Docker Compose listening on 127.0.0.1 only, with a test-named database and credentials supplied only through untracked environment variables. Compose samples SHALL NOT contain real passwords.

#### Scenario: Compose sample uses placeholders

- **WHEN** a compose test file is added
- **THEN** passwords are placeholders and documentation uses env vars

### Requirement: Pre-apply and pre-merge PostgreSQL verification

Before apply is approved and before merge, implementers SHALL verify PostgreSQL 16 connectivity and run integration tests. Lack of PostgreSQL SHALL block complete status.

#### Scenario: No silent SQLite substitution

- **WHEN** PostgreSQL is unavailable
- **THEN** production dialect checks are reported blocked rather than replaced by SQLite-only success

### Requirement: Backup and rollback guidance

Implementation docs SHALL state backup steps before production migration and prefer restore-from-backup for failed upgrades. Downgrade paths SHALL be tested on PostgreSQL.

#### Scenario: Downgrade then upgrade succeeds

- **WHEN** integration tests run alembic downgrade then upgrade head
- **THEN** both steps succeed

### Requirement: No secrets in repository

Migration files and tests SHALL NOT embed real database passwords.

#### Scenario: No password literals

- **WHEN** migration sources are scanned
- **THEN** no production password strings are present
