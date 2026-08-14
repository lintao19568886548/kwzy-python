## ADDED Requirements

### Requirement: Database-derived approval and audit permissions
The system SHALL authorize approval definition read/write, task read/decision, delegation management, audit read and audit export using current-tenant database role permissions and MUST ignore client-declared permissions, roles, assignees or audit scopes.

#### Scenario: Fabricated decision permission rejected
- **WHEN** a client without `approval.task.decide` declares that permission in a header or body and submits a decision
- **THEN** the system returns forbidden and persists no task, event, work-item, business or success-audit transition

#### Scenario: Audit export separated from read
- **WHEN** a role has `audit.read` but not `audit.export`
- **THEN** the user can search scoped rows but cannot export them

### Requirement: Approval override is explicit and auditable
Self-approval override SHALL require the database-derived `approval.task.override_self` permission plus a non-empty reason, and SHALL record both the normal decision event and a high-risk override audit summary.

#### Scenario: Star permission still requires reason
- **WHEN** a super-permission user self-approves without an override reason
- **THEN** the command is rejected and no approval transition commits
