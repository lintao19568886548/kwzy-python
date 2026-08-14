# Work Order Quotation Specification

## Purpose

Define exact, immutable and Party-scoped WorkOrder quotation versions and decisions.

## Requirements

### Requirement: Quotes use immutable submitted versions and exact totals
A quote SHALL contain Decimal quantity/unit-price lines with server-calculated line and header totals. Submitted versions SHALL be immutable; revisions create a new version and preserve every prior decision.

#### Scenario: Client-supplied total mismatch
- **WHEN** a quote payload claims a total different from its calculated lines
- **THEN** the server rejects the payload and persists no partial quote

### Requirement: Quote-required work cannot bypass tenant decision
When a WorkOrder requires quotation, diagnosis MAY start but fulfillment beyond the quote gate SHALL require one Party-bound accepted quote version.

#### Scenario: Technician starts quoted repair before acceptance
- **WHEN** no quote is accepted and execution is requested
- **THEN** the transition is rejected and the order remains waiting for quote decision

### Requirement: Tenant quote decisions are scoped and idempotent
Only the bound WorkOrder Party or authorized on-behalf staff SHALL accept or reject the current submitted quote. A decision requires aggregate/quote versions and an idempotency key.

#### Scenario: Another tenant accepts a quote
- **WHEN** a principal bound to another Party sends a quote decision
- **THEN** the quote is not disclosed and the request is denied

### Requirement: Rejected quotes require explicit revision
A rejected quote SHALL remain immutable and queryable. Continuing quoted work SHALL require a new submitted version and a new tenant decision.

#### Scenario: Edit rejected quote in place
- **WHEN** staff attempts to change lines on a rejected submitted version
- **THEN** the mutation is rejected and the original evidence is unchanged
