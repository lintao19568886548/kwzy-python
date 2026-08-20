# Inventory Ledger Control

## Purpose

Define immutable, reconciled, and concurrency-safe stock truth.

## Requirements

### Requirement: Append-only stock truth
The system SHALL record every stock change as an immutable typed movement and SHALL update the unique balance projection atomically.

#### Scenario: Inspect balance provenance
- **WHEN** an authorized user opens a material balance
- **THEN** the system exposes the ordered movement history whose sum reconciles to the balance

### Requirement: Non-negative available stock
The system SHALL prevent on-hand or available quantity from becoming negative under concurrent issue or reservation.

#### Scenario: Concurrent stock depletion
- **WHEN** concurrent requests together exceed available quantity
- **THEN** the database-serialized outcome rejects excess requests and preserves a non-negative balance

### Requirement: Stocktake and governed adjustment
The system SHALL snapshot expected quantity, calculate variance, require native approval for non-zero variance, and append an adjustment only after approval.

#### Scenario: Approve a variance
- **WHEN** an approved stocktake has a non-zero variance
- **THEN** one idempotent adjustment movement is appended and the balance reconciles to counted quantity

### Requirement: Reversal instead of mutation
The system SHALL correct an erroneous movement with a linked compensating reversal and SHALL never edit or delete the original movement.

#### Scenario: Reverse a receipt movement
- **WHEN** an authorized controller reverses an eligible movement
- **THEN** a linked opposite movement is appended and both records remain auditable
