# rent-control-portfolio-analysis Specification

## Purpose
Define reconciled, scoped vacancy, expiry and operating analysis projections derived from authoritative portfolio records.

## Requirements

### Requirement: Reconciled vacancy projection
The system SHALL list current visible units with positive available area and vacancy duration derived from source availability dates, using stable bounded pagination.

#### Scenario: Partially occupied unit
- **WHEN** a current unit has rentable area greater than effective occupied area
- **THEN** its remaining available area appears in vacancy results without changing the unit history

### Requirement: Source-linked expiry projection
The system SHALL list effective leases ending within a bounded date window with contract, party, unit and park source identifiers and SHALL exclude terminated or foreign records.

#### Scenario: Upcoming multi-unit lease
- **WHEN** an active contract has two visible units and ends inside the window
- **THEN** both unit relations are returned and reconcile to that one source contract

### Requirement: Portfolio operating analysis
The system SHALL aggregate current inventory and effective occupancy by category, usage type, status and spatial node, and SHALL label base-rent-derived potential separately from accounting revenue.

#### Scenario: Analysis reconciles
- **WHEN** an operator applies one park/subtree filter
- **THEN** inventory, rentable, used and available totals equal the corresponding current unit rows and category buckets

### Requirement: Scoped bounded filters
Vacancy, expiry and analysis queries SHALL enforce tenant/park scope, validate date/page/group bounds and use deterministic ordering.

#### Scenario: Foreign park filter
- **WHEN** a LIST-scoped user supplies another park id
- **THEN** the request exposes no counts, identifiers or timing metadata from that park
