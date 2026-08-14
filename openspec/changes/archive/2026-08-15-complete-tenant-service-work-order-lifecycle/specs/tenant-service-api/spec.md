## ADDED Requirements

### Requirement: Staff and tenant APIs are explicitly separated
Staff WorkOrder operations and tenant-principal service operations SHALL use separate route groups and response projections. Tenant routes SHALL never expose internal assignee phone, private cost, rule configuration or another Party's identifiers.

#### Scenario: Tenant detail projection
- **WHEN** a tenant principal reads its own request
- **THEN** only customer-visible status, quote, submitted evidence, acceptance and rating fields are returned

### Requirement: Request contracts are strict and bounded
All bodies SHALL forbid unknown fields, validate enum/length/Decimal/date bounds and reject duplicate query parameter names. Server-owned tenant, Party, totals, state, assignee and timestamps SHALL not be writable through generic payloads.

#### Scenario: Hidden status override
- **WHEN** intake includes `status=COMPLETED` or an unknown field
- **THEN** validation fails before any write

### Requirement: Child resources inherit aggregate scope
Quote, line, event, cost, acceptance and rating identifiers SHALL resolve through the tenant/park/Party-visible WorkOrder. Direct ids SHALL not widen scope.

#### Scenario: Foreign quote id under own order path
- **WHEN** a caller combines its order id with another tenant's quote id
- **THEN** the request returns non-disclosing denial and neither resource changes

### Requirement: Runtime and YAML contracts match
Mounted methods, paths, Idempotency-Key and expected-version requirements, response schemas and error codes SHALL match checked-in OpenAPI. No DELETE route SHALL erase WorkOrder evidence.

#### Scenario: Contract comparison
- **WHEN** runtime routes are compared with YAML
- **THEN** every tenant-service endpoint has an exact method match and no evidence DELETE method exists
