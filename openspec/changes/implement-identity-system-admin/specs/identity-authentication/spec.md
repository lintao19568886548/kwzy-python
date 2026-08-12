## ADDED Requirements

### Requirement: Password login with tenant disambiguation
The system SHALL authenticate username/password within an active tenant and SHALL require tenant_code when the username matches multiple tenants.

#### Scenario: Successful login
- **WHEN** a valid username/password for a single active tenant is submitted
- **THEN** the system returns access_token, refresh_token, expires_in, and user authorization summary

#### Scenario: Ambiguous tenant
- **WHEN** the same username exists in multiple active tenants without tenant_code
- **THEN** the system rejects with AUTH_TENANT_AMBIGUOUS

### Requirement: Password change revokes sessions
The system SHALL allow an authenticated user to change password when the old password matches and SHALL revoke outstanding refresh tokens and bump token_version.

#### Scenario: Password changed
- **WHEN** old_password is correct and new_password meets policy
- **THEN** password_hash updates, refresh tokens for that user are revoked, token_version increments
