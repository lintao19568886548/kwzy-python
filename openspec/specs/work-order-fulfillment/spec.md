# Work Order Fulfillment Specification

## Purpose

Define append-only fulfillment evidence, quote variance and governed completion submission.

## Requirements

### Requirement: Actual labor and material evidence is append-only
Fulfillment entries SHALL classify `LABOR`, `MATERIAL`, `OUTSOURCE` or `OTHER`, use positive Decimal quantity and non-negative unit price, calculate exact amount and record actor/time. Corrections SHALL use reversing entries with a reason and original reference.

#### Scenario: Correct material quantity
- **WHEN** a posted material entry is wrong
- **THEN** the original remains and a reasoned reversal plus corrected entry produces the current total

### Requirement: Quote and actual cost remain distinct
Accepted quotation totals SHALL represent agreed intent; actual entries SHALL represent execution evidence. The system SHALL expose variance without overwriting either history or decrementing inventory.

#### Scenario: Actual material exceeds quote
- **WHEN** actual material cost exceeds the accepted quote
- **THEN** the variance is visible and no stock or supplier settlement is fabricated

### Requirement: Completion submission requires bounded result evidence
An assignee SHALL provide a processing summary and safe evidence reference or explicit no-evidence reason before moving to `WAITING_ACCEPTANCE`. Submission SHALL close the field task and open a Party acceptance task atomically.

#### Scenario: Empty completion
- **WHEN** an assignee submits completion without summary or evidence/no-evidence reason
- **THEN** the request fails and state/tasks remain unchanged

### Requirement: Fulfillment mutations use current ownership and version
Only the current assignee or an authorized manager SHALL add execution entries or submit completion, and every transition SHALL require expected aggregate version.

#### Scenario: Former assignee posts labor
- **WHEN** a reassigned former worker submits an entry
- **THEN** the request is denied and no cost/timeline row is created
