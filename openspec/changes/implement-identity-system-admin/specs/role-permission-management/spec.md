## ADDED Requirements

### Requirement: Role and permission binding
The system SHALL allow authorized admins to manage roles and bind permission codes within the tenant.

#### Scenario: Bind permission
- **WHEN** identity.role.write binds a known permission code to a role
- **THEN** users with that role receive the permission on next authorization resolve
