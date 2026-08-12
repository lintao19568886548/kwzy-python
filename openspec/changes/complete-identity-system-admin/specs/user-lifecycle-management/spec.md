## ADDED Requirements

### Requirement: User administration APIs
The system SHALL provide tenant-scoped user administration APIs to list, create, update, and deactivate or delete users according to product rules approved at apply time. All user administration endpoints SHALL require authentication and explicit action permissions.

#### Scenario: List users within tenant
- **WHEN** an authorized admin lists users
- **THEN** only users belonging to the caller tenant are returned

#### Scenario: Create user requires permission
- **WHEN** a caller without user-manage permission attempts to create a user
- **THEN** the system returns 403 `PERMISSION_DENIED`

### Requirement: Username uniqueness within tenant
The system SHALL enforce username uniqueness within a tenant. Cross-tenant duplicate usernames MAY exist and MUST be disambiguated at login via `tenant_code`.

#### Scenario: Duplicate username in same tenant
- **WHEN** an admin creates a user with an existing username in the same tenant
- **THEN** the system rejects the create with a conflict business error

### Requirement: Password change and reset
The system SHALL support authenticated password change for the current user. Administrative password reset SHALL require elevated permission and MUST revoke or rotate existing refresh sessions when token-session security is enabled.

#### Scenario: Self password change
- **WHEN** an authenticated user submits a valid current password and a new password meeting policy
- **THEN** the password hash is updated and no plaintext password is returned

### Requirement: User enable and disable
The system SHALL support enabling and disabling users. Disabled users MUST NOT obtain new access tokens and SHOULD be blocked on refresh when refresh is implemented.

#### Scenario: Disabled user login
- **WHEN** a disabled user attempts password login
- **THEN** authentication fails
