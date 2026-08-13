## ADDED Requirements

### Requirement: Access token issuance
The system SHALL issue short-lived JWT access tokens containing tenant_id, user id, permissions, and park scope claims needed for fail-closed authorization. Tokens MUST NOT embed password hashes or other secrets.

#### Scenario: Access token claims present
- **WHEN** login succeeds
- **THEN** the access token decodes to claims including tenant_id and uid

### Requirement: Refresh tokens are opaque, rotated and revocable
The system SHALL issue cryptographically random opaque refresh tokens, store only their hashes, rotate them on every successful refresh, and revoke them on logout, password change, administrative reset, or user disable. A rotated token presented again SHALL be treated as potential replay and SHALL revoke the user's remaining refresh sessions.

#### Scenario: Rotated refresh token is replayed
- **WHEN** a client presents a refresh token that has already been replaced
- **THEN** the system returns 401 and revokes the user's remaining active refresh sessions

### Requirement: Refresh transport is client appropriate
The system SHALL support an HttpOnly SameSite cookie for PC browsers and MAY return the refresh token in the response body for non-browser mobile clients. Staging and production browser cookies SHALL be Secure. Both transports SHALL use the same rotation and revocation semantics.

#### Scenario: PC browser login
- **WHEN** a PC browser successfully logs in
- **THEN** the refresh credential is set in an HttpOnly cookie and the PC application does not persist it in localStorage

### Requirement: Logout and revocation
When refresh/session support is enabled, the system SHALL invalidate the presented refresh credential on logout and MUST prevent reuse of revoked refresh credentials.

#### Scenario: Logout revokes refresh
- **WHEN** an authenticated session logs out with a valid refresh credential
- **THEN** subsequent refresh attempts with the same credential fail

### Requirement: Access tokens support immediate session invalidation
Every protected request SHALL validate that the token user is active, belongs to the claimed tenant, and has a token_version equal to the current database value. Password reset, user disable, session revoke, and authorization changes SHALL increment the affected user's token_version.

#### Scenario: Disabled user's existing access token
- **WHEN** an administrator disables a user who still holds an unexpired access token
- **THEN** the next protected request with that token returns 401

### Requirement: Fail-closed authentication remains mandatory
The system SHALL continue to reject missing or invalid Bearer tokens in production and staging. Anonymous dev identity MUST remain limited to explicit local/test configuration and MUST NOT be available in production.

#### Scenario: Production missing token
- **WHEN** APP_ENV is production and a protected endpoint is called without Bearer
- **THEN** the system returns 401 `UNAUTHORIZED`
