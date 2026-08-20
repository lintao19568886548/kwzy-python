# Inventory Requisition and Issue

## Purpose

Define approved stock reservation, partial issue, return, and idempotent inventory operations.

## Requirements

### Requirement: Inventory requisition approval and reservation
The system SHALL support material requisitions linked optionally to a same-tenant same-park work order and SHALL reserve stock only through an authorized approval transition.

#### Scenario: Approve a requisition
- **WHEN** native approval succeeds and sufficient stock exists
- **THEN** requested quantities are reserved atomically without changing on-hand quantity

### Requirement: Partial and final issue
The system SHALL support partial and final issue, reduce on-hand and reserved quantities atomically, and append issue evidence.

#### Scenario: Partial issue
- **WHEN** an issuer supplies less than the approved remaining quantity
- **THEN** the issued quantity and balance update once while the requisition remains partially issued

### Requirement: Governed return
The system SHALL allow return only against prior issued quantity and SHALL append a separate return movement.

#### Scenario: Return more than issued
- **WHEN** a caller attempts to return more than the outstanding issued quantity
- **THEN** the system rejects the request without changing stock

### Requirement: Idempotent issue
The system SHALL return the original result for identical issue replay and SHALL reject key reuse with a different fingerprint.

#### Scenario: Conflicting key reuse
- **WHEN** an idempotency key is reused with a different quantity
- **THEN** the system returns conflict and creates no additional movement
