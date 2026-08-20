# Supply API

## ADDED Requirements

### Requirement: Mounted strict HTTP API
The system SHALL mount versioned supply endpoints with strict request schemas, stable error envelopes, bounded paging, and published OpenAPI contracts.

#### Scenario: Send an unknown field
- **WHEN** a mutation body contains a field outside its schema
- **THEN** the API returns validation error and performs no write

### Requirement: Database-derived authorization
The system SHALL derive supply permissions and park scope from authenticated database state on every request.

#### Scenario: Forge a permission header
- **WHEN** a caller supplies client-controlled role or permission headers
- **THEN** the headers grant no authority

### Requirement: Cross-boundary non-disclosure
The system SHALL return not found for tenant/park foreign resource identifiers and SHALL reject bulk payloads atomically when any item is outside scope.

#### Scenario: Mixed-scope receipt lines
- **WHEN** one receipt payload includes a foreign purchase-order line
- **THEN** the entire request is rejected with no partial stock movement

### Requirement: Sensitive-field and audit safety
The system SHALL mask credentials and PII in responses and logs and SHALL record actor, time, action, target, and correlation evidence for privileged transitions.

#### Scenario: Inspect request logs
- **WHEN** a supplier qualification mutation is logged
- **THEN** raw credential values are absent while audit correlation remains available
