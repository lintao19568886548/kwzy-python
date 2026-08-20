# Purchase Order and Receipt

## Purpose

Define approved-source purchase orders and concurrency-safe receipt-driven inventory increases.

## Requirements

### Requirement: Approved-source purchase order
The system SHALL create a purchase order only from an approved requisition, an eligible supplier, and immutable commercial line snapshots.

#### Scenario: Create a local purchase order
- **WHEN** an authorized buyer uses an approved requisition and eligible supplier
- **THEN** the system creates a local-truth order with ordered and received quantities separated

### Requirement: Governed acknowledgement
The system SHALL record supplier acknowledgement or rejection as auditable transitions and SHALL not imply a live supplier portal without an adapter.

#### Scenario: Mark external acknowledgement pending
- **WHEN** an order is configured for an unavailable external adapter
- **THEN** the order remains explicitly pending external acknowledgement and is not reported as acknowledged

### Requirement: Atomic receipt and stock increase
The system SHALL lock affected order lines and balances, reject over-receipt, create receipt evidence and append stock movements in one transaction.

#### Scenario: Concurrent final receipt
- **WHEN** two requests concurrently try to receive the same remaining quantity
- **THEN** at most one succeeds and total received never exceeds ordered quantity

#### Scenario: Replay receipt
- **WHEN** an identical receipt is replayed with the same idempotency key
- **THEN** no duplicate receipt, movement, or stock increase is created
