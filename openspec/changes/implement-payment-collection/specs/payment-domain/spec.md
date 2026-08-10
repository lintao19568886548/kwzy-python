## ADDED Requirements

### Requirement: Payment is collection registration
Payment SHALL record operational receipt amount, method, and status CONFIRMED or REVERSED. It SHALL NOT represent an online checkout order.

#### Scenario: Allocate to bill
- **WHEN** a confirmed payment allocates amount A to an ISSUED bill
- **THEN** bill.paid_amount increases by A and status is recomputed

#### Scenario: Reverse payment
- **WHEN** a confirmed payment is reversed
- **THEN** allocations are unwound and bill paid_amount decreases
