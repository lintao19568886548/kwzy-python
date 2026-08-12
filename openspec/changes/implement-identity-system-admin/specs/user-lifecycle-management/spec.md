## ADDED Requirements

### Requirement: Tenant user administration
The system SHALL allow authorized admins to list, create, update, and disable users inside their tenant only.

#### Scenario: Create user
- **WHEN** an admin with identity.user.write creates a user with unique username in tenant
- **THEN** the user is persisted with hashed password and optional role/park grants

#### Scenario: Cross-tenant isolation
- **WHEN** a user id belongs to another tenant
- **THEN** admin APIs return 404 or 403 without leaking existence details beyond tenant boundary
