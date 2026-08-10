## ADDED Requirements

### Requirement: Bill statuses exclude OVERDUE
Bill status SHALL be DRAFT, ISSUED, PARTIALLY_PAID, PAID, VOID, or DISCARDED. OVERDUE SHALL NOT be a status value. Overdue SHALL be computed as is_overdue.

#### Scenario: Issue draft
- **WHEN** an authorized user issues a DRAFT bill with at least one line
- **THEN** status becomes ISSUED and total_amount equals sum of line amounts

#### Scenario: Void issued unpaid
- **WHEN** an ISSUED bill with paid_amount=0 is voided
- **THEN** status becomes VOID
