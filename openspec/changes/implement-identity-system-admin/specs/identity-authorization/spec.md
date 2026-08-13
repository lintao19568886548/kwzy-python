## ADDED Requirements

### Requirement: Permission gate on admin writes
The system SHALL require explicit permission codes for identity admin mutations and SHALL treat `*` as all actions without granting all parks.

#### Scenario: Missing permission
- **WHEN** a user without identity.user.write calls create user
- **THEN** the system returns 403 PERMISSION_DENIED
