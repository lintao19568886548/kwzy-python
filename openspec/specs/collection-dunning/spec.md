# collection-dunning Specification

## Purpose
TBD - created by archiving change complete-receivables-collection-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Aging level is derived from effective due date
The system SHALL derive L1 for 1-7 days, L2 for 8-30, L3 for 31-60 and L4 for 61+ overdue days from effective due date and collectible open amount. Bill payment status SHALL NOT be replaced with an overdue enum.

#### Scenario: Partially paid 35-day Bill
- **WHEN** a partially paid Bill remains collectible 35 days after effective due date
- **THEN** its collection level is L3 while its Bill status remains PARTIALLY_PAID

### Requirement: Dunning runs are previewable and repeat safe
A dunning run SHALL support preview and apply. Apply requires `collection:run`, creates or escalates at most one active case per Bill, appends one SYSTEM record per run/level and creates a work item without duplicate side effects.

#### Scenario: Repeat same-day run
- **WHEN** the same as-of/park run is applied twice
- **THEN** no duplicate active case, action record or work item is created

### Requirement: Collection history is append only
Cases SHALL retain amount/aging snapshots, assignee, current level and status. Calls, visits, messages, notices, system escalation, failure and acknowledgement SHALL be append-only records; normal APIs SHALL not delete history.

#### Scenario: Failed external delivery
- **WHEN** an unconfigured provider is selected for a collection action
- **THEN** the record reports failure/not-configured and is not presented as sent

### Requirement: Holds and settlement control automation
Disputed, collection-held, not-yet-due after approved extension, void/discarded or fully settled Bills SHALL not be escalated. Settlement SHALL close the active case and work item; a valid reversal that reopens the receivable SHALL reopen collection eligibility.

#### Scenario: Approved extension
- **WHEN** a Bill effective due date is extended beyond the run date
- **THEN** the dunning run skips it and records no escalation
