## ADDED Requirements

### Requirement: Refresh token rotation
The system SHALL issue opaque refresh tokens stored only as hashes and SHALL rotate them on successful refresh.

#### Scenario: Refresh success
- **WHEN** a valid non-revoked refresh token is presented
- **THEN** a new access_token and new refresh_token are returned and the previous refresh token is revoked

#### Scenario: Refresh revoked
- **WHEN** a revoked or unknown refresh token is presented
- **THEN** the system rejects with 401

### Requirement: Logout revokes refresh
The system SHALL revoke the presented refresh token on logout.

#### Scenario: Logout
- **WHEN** logout is called with a valid refresh token
- **THEN** that token cannot be used to refresh again
