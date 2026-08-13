## ADDED Requirements

### Requirement: Role administration
The system SHALL provide tenant-scoped role create, read, update, and delete (or deactivate) APIs. Role changes SHALL be audited on successful writes.

#### Scenario: Create role
- **WHEN** an authorized admin creates a role with a unique code in the tenant
- **THEN** the role is persisted and visible in subsequent list calls

### Requirement: Role-permission binding
The system SHALL allow binding and unbinding permission codes to roles. Permission codes SHALL be string action identifiers. The special code `*` SHALL mean all action permissions and MUST NOT imply all-park data scope.

#### Scenario: Bind permissions to role
- **WHEN** an admin adds permission codes to a role
- **THEN** users holding that active role receive those codes on next authorization resolution according to token-session policy

#### Scenario: Star is action-only
- **WHEN** a role has permission `*` but no all-parks grant
- **THEN** park scope remains not ALL solely due to `*`

### Requirement: Permission catalog visibility
The system SHALL expose a permission code list usable by administration UIs either as a dedicated catalog endpoint or as documented seed data with a list API. Exact catalog source is an apply-time decision documented in design.

#### Scenario: Admin reads permission codes
- **WHEN** an authorized admin requests permission codes
- **THEN** the response contains codes without secrets
