## ADDED Requirements

### Requirement: Git hygiene runbook without remote publish
This change SHALL provide an operator runbook for initializing a local Git repository for `kwzy-python` that does not configure a remote or push to GitHub.

#### Scenario: Runbook forbids remote push in this phase
- **WHEN** the Git hygiene tasks are read
- **THEN** they instruct no remote configuration and no push in this change

### Requirement: Sensitive and database files must not be committed
The recommended `.gitignore` and runbook SHALL exclude environment secrets, SQLite databases, database backups, virtualenvs, caches, logs, and IDE private files from version control.

#### Scenario: Database files ignored
- **WHEN** `.gitignore` recommendations from this change are applied
- **THEN** `*.db`, timestamped `*.backup*.db` patterns, and `.env` are ignored

### Requirement: Baseline commit is optional and manual
Creating the initial Step1 baseline commit SHALL be listed as a manual operator step after ignore rules are in place, and SHALL NOT be executed by the proposal phase.

#### Scenario: Propose phase does not create git repo
- **WHEN** only the OpenSpec proposal artifacts of this change are created
- **THEN** no `git init` or commit is performed by that step
