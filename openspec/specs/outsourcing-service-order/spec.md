# Outsourcing Service Order

## Purpose

Define approval-governed outsourcing execution, acceptance, evaluation, and settlement boundaries.

## Requirements

### Requirement: Governed outsourcing order
The system SHALL bind an outsourcing order to tenant, park, eligible supplier, optional work order, SLA, deliverable, and commercial snapshots.

#### Scenario: Submit an outsourcing order
- **WHEN** an authorized operator submits a complete draft with an eligible supplier
- **THEN** the immutable snapshot is stored and a native approval instance is created

### Requirement: Append-only execution lifecycle
The system SHALL retain ordered execution events and enforce valid transitions from approval through execution, completion, acceptance, rework, or cancellation.

#### Scenario: Complete service delivery
- **WHEN** an executor records required deliverables and completion
- **THEN** the order enters waiting acceptance and cannot be reported as accepted

#### Scenario: Reject service delivery
- **WHEN** an authorized acceptor rejects completed delivery with a reason
- **THEN** a rework event is appended and the order returns to execution

### Requirement: Acceptance and evaluation
The system SHALL permit same-park authorized acceptance once and may append a supplier evaluation without overwriting prior evaluations.

#### Scenario: Duplicate acceptance
- **WHEN** acceptance is replayed
- **THEN** idempotency returns the first result and no duplicate evaluation is created

### Requirement: Settlement boundary
The system SHALL expose invoice and payment settlement as unavailable unless a governed integration exists.

#### Scenario: Read accepted local order
- **WHEN** an accepted order has no settlement adapter
- **THEN** the API reports settlement as not integrated rather than paid
