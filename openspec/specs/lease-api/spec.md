# lease-api Specification

## Purpose
定义基础租赁合同在 `/api/v1` 下的接口封装、权限、租户与园区范围、审计和安全日志规则。该规格确保合同读写采用统一错误语义和请求追踪，并且跨租户或越园区访问不会泄露业务数据。
## Requirements
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

### Requirement: Sign command returns envelope truth
`POST /leases/{contract_id}/documents/{document_id}/sign` SHALL return linked signature envelope id, status, provider status and `live_verified` together with the lease detail. It SHALL not describe sandbox completion as live signed.

#### Scenario: Sandbox response
- **WHEN** the sign command runs under the local sandbox adapter
- **THEN** the response reports SANDBOX_COMPLETED and live_verified false while the source document status is APPROVED

### Requirement: Signature provider failures are stable and retryable
Missing provider configuration, timeout, rejected event and unavailable evidence SHALL return documented stable error codes without changing the lease document to SIGNED. Same command replay SHALL not create multiple envelopes.

#### Scenario: Provider not configured
- **WHEN** a production sign command has no CONNECTED provider
- **THEN** the API returns 503 `SIGNATURE_PROVIDER_NOT_CONFIGURED` and leaves document evidence unchanged
