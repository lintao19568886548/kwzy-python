## ADDED Requirements

### Requirement: Access token issuance
The system SHALL issue short-lived JWT access tokens containing tenant_id, user id, permissions, and park scope claims needed for fail-closed authorization. Tokens MUST NOT embed password hashes or other secrets.

#### Scenario: Access token claims present
- **WHEN** login succeeds
- **THEN** the access token decodes to claims including tenant_id and uid

### Requirement: Refresh token lifecycle is decision-gated
The system SHALL implement refresh token issuance, rotation, and logout/revocation only after the storage mechanism (HTTP-only cookie vs body), persistence store, and revocation model are approved. Until approval, refresh/logout remain specified as required capabilities but MUST be marked not production-COMPLETE.

#### Scenario: Refresh without approved design blocked
- **WHEN** refresh storage decision is unresolved
- **THEN** apply tasks for refresh MUST remain blocked by an explicit human decision checkpoint

### Requirement: Logout and revocation
When refresh/session support is enabled, the system SHALL invalidate the presented refresh credential on logout and MUST prevent reuse of revoked refresh credentials.

#### Scenario: Logout revokes refresh
- **WHEN** an authenticated session logs out with a valid refresh credential
- **THEN** subsequent refresh attempts with the same credential fail

### Requirement: Fail-closed authentication remains mandatory
The system SHALL continue to reject missing or invalid Bearer tokens in production and staging. Anonymous dev identity MUST remain limited to explicit local/test configuration and MUST NOT be available in production.

#### Scenario: Production missing token
- **WHEN** APP_ENV is production and a protected endpoint is called without Bearer
- **THEN** the system returns 401 `UNAUTHORIZED`
