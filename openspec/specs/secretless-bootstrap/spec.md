# secretless-bootstrap Specification

## Purpose
TBD - created by archiving change close-step1-acceptance-gaps. Update Purpose after archive.
## Requirements
### Requirement: No fixed admin plaintext password in source
The codebase SHALL NOT contain a fixed administrator plaintext password used for bootstrap hashing or comparison.

#### Scenario: Source has no hardcoded bootstrap password literal for admin seed
- **WHEN** bootstrap/admin seed implementation is reviewed or statically checked
- **THEN** it does not embed a fixed admin password string used as the seed credential

### Requirement: Local bootstrap password from environment
In `local` environment, creating a new default admin user SHALL read the initial password only from a dedicated environment variable (for example `LOCAL_ADMIN_PASSWORD`).

#### Scenario: Local creates admin when password env is set
- **WHEN** `APP_ENV=local`, default tenant bootstrap runs, admin user does not exist, and the password environment variable is non-empty
- **THEN** the admin user is created with a hash derived from that environment value

#### Scenario: Local does not silently use a fixed password when env missing
- **WHEN** `APP_ENV=local`, admin user does not exist, and the password environment variable is missing or empty
- **THEN** the system SHALL NOT create the admin with any fixed built-in password; it SHALL fail closed for that create path or skip admin creation with an explicit error/warning log

### Requirement: Test credentials from fixtures
In `test` environment, admin or user credentials used by tests SHALL be supplied by test fixtures or test environment configuration, not by production source constants.

#### Scenario: Tests supply credentials
- **WHEN** authorization tests need an admin password
- **THEN** they obtain it from fixture/env configuration rather than a shared hardcoded production default in library code

### Requirement: Idempotent existing admin password
If the default admin user already exists, bootstrap SHALL leave its password hash unchanged.

#### Scenario: Existing admin not reset
- **WHEN** bootstrap runs and admin already exists
- **THEN** the stored password hash is not overwritten

### Requirement: Production forbids automatic admin seed
When `APP_ENV=production`, application startup SHALL NOT automatically seed default tenant admin users or roles.

#### Scenario: Production startup without seed
- **WHEN** the application starts with `APP_ENV=production`
- **THEN** the default admin bootstrap seed is not executed

### Requirement: Secrets never leak through observability surfaces
Administrator passwords and password hashes SHALL NOT appear in logs, audit detail payloads, API responses, or committed documentation examples as real secrets.

#### Scenario: Audit and logs exclude password material
- **WHEN** bootstrap or login-related code emits logs or audit details
- **THEN** the payloads do not include plaintext passwords or reusable secret material

### Requirement: Env example is placeholder-only
`.env.example` MAY document the password environment variable name but SHALL NOT provide a real default password value.

#### Scenario: Example file has empty or placeholder password
- **WHEN** `.env.example` is inspected
- **THEN** the admin password variable is empty or an obvious non-secret placeholder, not a usable real password

