## ADDED Requirements

### Requirement: Facility operations APIs are explicit and strict
Mounted device, template, schedule, inspection, provider, binding and alarm routes SHALL use explicit request schemas that forbid unknown fields, bound strings/lists/Decimal/dates and reject duplicate query parameters. Server-owned scope, state, counts, totals and versions SHALL not be generally writable.

#### Scenario: Hidden alarm status override
- **WHEN** an ingestion body includes a server-owned alarm status or unknown field
- **THEN** validation fails before an event or alarm is written

### Requirement: Permissions and park scope are database derived
Read and mutation routes SHALL enforce database role permissions and effective park grants. Token claims SHALL not expand persisted authority, and ALL scope SHALL still be restricted to parks owned by the current tenant.

#### Scenario: Forged ingest permission
- **WHEN** a user without persisted `iot:ingest` permission presents that permission in a forged token claim
- **THEN** ingestion is forbidden and no source event exists

### Requirement: Child identifiers inherit aggregate scope
Template items, schedules, task results, exceptions, provider bindings, alarm events and linked WorkOrders SHALL resolve through their tenant/park-visible parent. Direct child ids SHALL not widen access or permit mixed-parent writes.

#### Scenario: Foreign binding under own provider
- **WHEN** a caller combines its provider id with another tenant's binding id
- **THEN** the request is denied without disclosing or changing the foreign binding

### Requirement: Runtime and YAML methods match without evidence deletion
Runtime methods, paths, headers, expected-version/idempotency requirements, response projections and error codes SHALL exactly match checked-in OpenAPI. No DELETE method SHALL physically remove device, inspection or alarm evidence.

#### Scenario: Facility contract comparison
- **WHEN** mounted facility routes are compared with YAML
- **THEN** every method matches and no evidence DELETE route exists
