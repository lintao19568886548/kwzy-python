## ADDED Requirements

### Requirement: Disabled-by-default channel configuration
The system SHALL manage tenant-owned channel configurations with an unguessable public id, explicit enabled state, default authorized park, bounded source mapping and environment-key references instead of stored plaintext secrets.

#### Scenario: Channel has no usable secret
- **WHEN** a configured channel is enabled but its referenced environment secret is absent
- **THEN** intake fails closed with no Lead or successful receive record

### Requirement: Signed bounded intake
The public intake endpoint SHALL verify HMAC-SHA256 over timestamp, external event id and raw body digest using constant-time comparison, enforce clock skew and body/field limits, and reject unknown mappings before business mutation.

#### Scenario: Forged signature
- **WHEN** an event has an invalid signature, stale timestamp or altered body
- **THEN** the endpoint returns an authentication failure and creates no Lead or success audit

### Requirement: Idempotent receive and normalized Lead creation
For an enabled valid channel, `(channel_id, external_event_id)` SHALL identify one inbox event; accepted normalized facts SHALL create or reuse exactly one Lead with server-controlled park, source and assignment behavior.

#### Scenario: Provider retries accepted event
- **WHEN** the same signed external event is delivered twice
- **THEN** both responses refer to the same inbox result and Lead with no duplicate assignment or activity

#### Scenario: Payload attempts owner injection
- **WHEN** a validly signed payload includes owner, permissions, approval status, lock or contract fields
- **THEN** those fields are rejected or ignored according to the allow-list and cannot bypass server rules

### Requirement: Quarantine and controlled replay
Validated signatures with unmappable business data SHALL produce a bounded QUARANTINED inbox record containing digest and stable reason without raw secrets, and only a channel replay permission SHALL reprocess it idempotently after configuration correction.

#### Scenario: Unknown park mapping
- **WHEN** a signed event cannot map to an authorized park
- **THEN** it is quarantined without creating a Lead and a later authorized replay can succeed at most once

### Requirement: Truthful external status
Channel APIs and UI SHALL distinguish local contract verification from live provider verification and MUST NOT report a provider as connected without separately recorded sandbox or production evidence.

#### Scenario: Local HMAC fixture passes
- **WHEN** an isolated test sender completes the signed intake journey
- **THEN** the status remains `LOCAL_CONTRACT_VERIFIED` rather than `LIVE_CONNECTED`
