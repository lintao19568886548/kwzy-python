## ADDED Requirements

### Requirement: Strict mounted workforce API
The system SHALL mount strict, bounded, unified workforce routes under `/api/v1/workforce` with exact runtime/YAML parity.

#### Scenario: Unknown field or repeated scalar query
- **WHEN** a client submits either
- **THEN** validation fails before mutation

### Requirement: Permissions and scope are database derived
Distinct workforce permissions SHALL be resolved from database grants and tenant/park/parent scope SHALL return 404 for invisible resources.

#### Scenario: Forged review permission
- **WHEN** a token adds an ungranted review permission
- **THEN** the API returns 403

### Requirement: Commands are concurrency safe
Mutations SHALL use tenant-scoped idempotency and/or expected versions, with equal replay returning the prior result and changed/stale state returning 409.

#### Scenario: Changed idempotency payload
- **WHEN** one key is reused with changed content
- **THEN** the first command is preserved and 409 returned
