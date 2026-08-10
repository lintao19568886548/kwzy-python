## ADDED Requirements

### Requirement: Nested REST API under /api/v1
Lease APIs SHALL be exposed under /api/v1 with unified envelope {code, message, data}, AppError codes, and X-Request-Id propagation.

#### Scenario: List requires lease:read
- **WHEN** a user without lease:read lists contracts
- **THEN** the API returns 403

### Requirement: Tenant and park scope
All lease queries and writes SHALL enforce tenant_id from TenantContext and park scope for contract.park_id. Empty park scope SHALL not mean all parks.

#### Scenario: Cross-tenant contract hidden
- **WHEN** tenant A requests a contract id belonging to tenant B
- **THEN** the API returns 404

### Requirement: Audit and logging without secrets
Successful write operations SHALL write audit records and business logs with request_id, tenant_id, user_id, module=lease, action, resource_id without dumping secrets or full PII address lines.

#### Scenario: Create audited
- **WHEN** a contract is created
- **THEN** an audit log row exists for the create action
