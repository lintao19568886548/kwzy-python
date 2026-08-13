## ADDED Requirements

### Requirement: Consistent rent-control metrics
The system SHALL calculate inventory count, rentable area, used area, available area and occupancy rate from current non-deleted unit versions visible to the caller. Occupancy rate SHALL be used area divided by rentable area, with zero returned when rentable area is zero.

#### Scenario: Summary reconciles with rows
- **WHEN** a scoped user queries rent control for a park
- **THEN** summary areas equal the sum of the returned/filter-matching current units and status buckets reconcile to inventory count

### Requirement: Operational filtering and pagination
Rent-control queries SHALL support park, spatial subtree, status, usage type and keyword filters with stable pagination and deterministic ordering.

#### Scenario: Spatial subtree filter
- **WHEN** a user selects a building node
- **THEN** the result contains only current units bound to that building or its descendant floors

### Requirement: Unit operational detail
The system SHALL expose a scoped unit detail containing current attributes, version history, split/merge lineage, effective lease/Party summary and related work-order summary when those relations exist. A missing or out-of-scope relation SHALL not leak foreign data.

#### Scenario: Occupied unit is drilled down
- **WHEN** an authorized user opens an occupied unit
- **THEN** the response includes its current lease number, Party display name, occupied area and historical unit versions

### Requirement: Status semantics are explicit
The rent-control response SHALL distinguish DRAFT, VACANT, RESERVED, OCCUPIED, MAINTENANCE and RETIRED semantics and SHALL use current effective versions for operational totals while retaining retired/history rows only in drill-down history.

#### Scenario: Retired source is excluded from inventory
- **WHEN** a source unit has been retired by split or merge
- **THEN** it is absent from operational inventory totals but present in lineage/history queries
