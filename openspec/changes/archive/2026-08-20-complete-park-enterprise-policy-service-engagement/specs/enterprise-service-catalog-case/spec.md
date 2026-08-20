## ADDED Requirements

### Requirement: Versioned service catalogue and provider truth
The system SHALL publish immutable service versions with park scope, category, eligibility, SLA, appointment rules, evidence requirements, price truth, and an internal or explicitly unconnected external provider state.

#### Scenario: Read an external-provider service
- **WHEN** a visible service has no governed provider adapter
- **THEN** the catalogue reports `NOT_CONNECTED` and does not claim live booking, fulfillment, price confirmation, or payment

### Requirement: Persisted Party-bound service request
Tenant-principal service requests SHALL derive tenant, Party, parks, and contact projection from persisted grants, require a request fingerprint, and reject authoritative Party or provider overrides from the body.

#### Scenario: Forge another Party
- **WHEN** a tenant principal submits another Party identifier or an inaccessible park
- **THEN** the request fails without creating a service case, appointment, event, or notification

### Requirement: Append-only case, SLA, and appointment lifecycle
The system SHALL retain ordered case events for acceptance, assignment, appointment, evidence, progress, result, rejection, cancellation, and SLA escalation with valid transitions and optimistic concurrency.

#### Scenario: Concurrent appointment confirmation
- **WHEN** two operators confirm different appointment slots for the same pending case version
- **THEN** at most one transition succeeds and both attempts remain traceable without conflicting active appointments

### Requirement: Result confirmation and feedback
The system SHALL expose customer-visible result evidence, allow one governed confirmation or reasoned dispute, and append at most one Party feedback record without treating a linked repair WorkOrder or external settlement as completed service evidence.

#### Scenario: Confirm a completed local service
- **WHEN** the bound tenant principal confirms the delivered result
- **THEN** the case closes locally and any external provider, payment, or government state remains separately unavailable unless verified
