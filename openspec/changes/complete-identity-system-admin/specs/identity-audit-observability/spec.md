## ADDED Requirements

### Requirement: Audit successful identity admin writes
The system SHALL record audit events for successful identity administration writes including user create/update/disable, role changes, permission binds, menu writes, and park-scope grants. Audit records SHALL include tenant_id, actor user id, action, target type/id, and request_id when available.

#### Scenario: Role permission bind audited
- **WHEN** an admin successfully binds permissions to a role
- **THEN** an audit record is persisted without storing password or token secrets

### Requirement: Failed sensitive auth attempts are observable
The system SHALL ensure failed login attempts are observable via structured logs and MAY create audit records per product policy. Logs MUST NOT include password plaintext or full refresh tokens.

#### Scenario: Failed login log hygiene
- **WHEN** password login fails
- **THEN** logs do not contain the submitted password

### Requirement: Sensitive fields excluded from API responses
The system SHALL NOT return password hashes, refresh token secrets, or SMS codes in API success payloads. User list and detail responses MUST omit password_hash.

#### Scenario: User detail has no password hash
- **WHEN** an admin retrieves a user
- **THEN** the response body does not include password_hash
