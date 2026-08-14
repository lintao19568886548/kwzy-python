# receivables-api Specification

## Purpose
TBD - created by archiving change complete-receivables-collection-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Receivables APIs are strict and mounted
The runtime SHALL expose strict envelope-based routes for billing runs, receipt capabilities/import/list/detail/match/review/dispute, later Payment allocations, dunning runs/cases/records and receivable adjustments. Unknown fields, client tenant ids and ambiguous duplicate query parameters SHALL be rejected.

#### Scenario: Client tenant pollution
- **WHEN** a receipt or adjustment body contains tenant_id
- **THEN** validation rejects the request and no write occurs

### Requirement: Finance identifiers do not leak across tenant or park scope
List, detail and command routes SHALL resolve every receipt, Payment, Bill, case, record and adjustment through authenticated tenant and park scope. Foreign identifiers SHALL return not found/denied without resource-owner leakage.

#### Scenario: Cross-tenant receipt id
- **WHEN** a caller requests another tenant's valid receipt id
- **THEN** the API returns not found or denied without receipt fields

### Requirement: Permission boundaries follow finance roles
Generation, import, match review, allocation, dispute review, dunning run and receivable adjustment SHALL each require their documented database-derived permission in addition to park scope. `*` remains the only action super-permission.

#### Scenario: Collection operator confirms money
- **WHEN** a collection-only role attempts receipt confirmation
- **THEN** the request is denied and no Payment is created

### Requirement: Runtime and checked-in OpenAPI agree
The runtime method set, request bounds, response schemas, Idempotency-Key requirements and error codes for all new routes SHALL match checked-in OpenAPI. No DELETE endpoint SHALL erase financial evidence.

#### Scenario: Contract comparison
- **WHEN** runtime routes are compared with YAML
- **THEN** every receivables endpoint has an exact method match and no evidence DELETE method exists
