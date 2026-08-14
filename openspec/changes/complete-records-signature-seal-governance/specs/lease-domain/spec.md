## ADDED Requirements

### Requirement: Lease signing delegates to governed envelope truth
An APPROVED lease document SHALL create or reference an electronic-signature envelope bound to its exact checksum. A local/sandbox result SHALL NOT append a legal `SIGNED` lease document version. Only a `COMPLETED` envelope with `live_verified=true` MAY produce a `SIGNED` version.

#### Scenario: Local sign command
- **WHEN** an APPROVED lease document is signed through the local sandbox provider
- **THEN** a SANDBOX_COMPLETED envelope is recorded and the lease document remains APPROVED

### Requirement: Lease activation uses truthful document evidence
Any lease rule that requires signed evidence SHALL distinguish approved, sandbox-completed and live-verified signed documents. Sandbox evidence MAY satisfy local test setup only when explicitly configured, and SHALL be identified in responses and audit.

#### Scenario: Production activation with sandbox evidence
- **WHEN** production activation requires a signed contract but only sandbox evidence exists
- **THEN** activation fails closed with a provider/evidence error
