# facility-device-registry Specification

## Purpose
TBD - created by archiving change complete-facility-device-inspection-iot. Update Purpose after archive.
## Requirements
### Requirement: Facility devices use one governed identity
The system SHALL represent supported fire, elevator, transformer, electrical, HVAC, water, security and custom equipment as one FacilityDevice aggregate with tenant, park, optional unit, stable device code, name, type, location, criticality and lifecycle state.

#### Scenario: Register a transformer
- **WHEN** an authorized operator registers a transformer in an allowed park with a unique device code and bounded type properties
- **THEN** one ACTIVE device is created with the tenant/park/unit ownership recorded

### Requirement: Type properties are bounded and server validated
Device-specific properties SHALL use server-owned type profiles with bounded keys, values, depth and size. Server-owned identity, status, tenant, history and version fields SHALL not be writable through the properties payload.

#### Scenario: Hidden state in custom properties
- **WHEN** a client includes `status` or an unknown nested property in type properties
- **THEN** validation fails before any device row or history row is written

### Requirement: Device changes preserve immutable history
Material device updates SHALL require the expected lock version and append a before/after history record with actor, reason and time. Concurrent updates to the same version SHALL have exactly one winner.

#### Scenario: Concurrent location edits
- **WHEN** two users update the same device version to different locations
- **THEN** one update commits with one history entry and the other receives a version conflict

### Requirement: Retirement preserves active evidence
Devices SHALL be retired by a reasoned state transition rather than physical deletion. Retirement SHALL be rejected while an inspection task or alarm is active, and historical tasks, results, bindings, alarms and WorkOrders SHALL remain queryable.

#### Scenario: Retire device with open alarm
- **WHEN** an operator attempts to retire a device that has an OPEN alarm
- **THEN** the operation fails and neither the device nor alarm evidence changes
