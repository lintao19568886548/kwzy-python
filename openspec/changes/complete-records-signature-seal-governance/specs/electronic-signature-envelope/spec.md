## ADDED Requirements

### Requirement: Provider status is truthful and secretless
Providers SHALL persist adapter kind, status `NOT_CONNECTED/SANDBOX/CONNECTED/DEGRADED`, environment credential reference and bounded health facts, never secret values. `CONNECTED` SHALL require supported configuration and verified health.

#### Scenario: Missing production credential
- **WHEN** a production provider credential reference cannot be resolved
- **THEN** dispatch fails closed and provider is not reported CONNECTED

### Requirement: Envelopes bind exact record revisions and participants
Each envelope SHALL reference one filed record revision checksum, provider, purpose and ordered participants with role and masked contact metadata. Revision changes SHALL require a new envelope.

#### Scenario: Envelope created from draft record
- **WHEN** dispatch is requested for a record that is not FILED
- **THEN** the request is rejected and no provider event is fabricated

### Requirement: Sandbox completion is not legal completion
Envelope status SHALL distinguish `SANDBOX_COMPLETED` from verified `COMPLETED`. `live_verified=true` and downstream legal `SIGNED` status SHALL be possible only after an authenticated event from a CONNECTED provider.

#### Scenario: Local sandbox dispatch
- **WHEN** a local adapter completes an envelope
- **THEN** status is SANDBOX_COMPLETED, live_verified is false and the source lease document remains APPROVED

### Requirement: Provider events are authenticated and replay safe
Accepted events SHALL be append-only and unique by tenant/provider/source event id with canonical payload hash. Exact replay returns the existing result; a changed payload under the same id conflicts. No anonymous generic callback SHALL be mounted.

#### Scenario: Changed replay
- **WHEN** an authorized ingest repeats a source id with a different payload hash
- **THEN** the API returns conflict and envelope evidence is unchanged
