# Procurement Requisition Approval

## ADDED Requirements

### Requirement: Immutable submitted requisition
The system SHALL allow editable draft requisitions but SHALL freeze requester, park, purpose, and line snapshots at submission.

#### Scenario: Submit a valid requisition
- **WHEN** an authorized requester submits a non-empty draft with valid materials and positive quantities
- **THEN** the system stores the immutable snapshot and creates a native approval instance atomically

#### Scenario: Modify a submitted requisition
- **WHEN** a caller attempts to edit a submitted requisition
- **THEN** the system rejects the transition and preserves the submitted snapshot

### Requirement: Native approval result
The system SHALL derive approved or rejected state from the platform approval aggregate and SHALL not accept a client-supplied approval result.

#### Scenario: Create order before approval
- **WHEN** a caller tries to create a purchase order from a pending or rejected requisition
- **THEN** the system rejects the request with no order residue

### Requirement: Idempotent submission
The system SHALL bind each mutation idempotency key to a request fingerprint.

#### Scenario: Replay submission
- **WHEN** the same key and identical payload are replayed
- **THEN** the original response is returned without a second approval instance
