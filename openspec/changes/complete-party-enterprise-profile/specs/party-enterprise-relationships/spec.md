## ADDED Requirements

### Requirement: Related-company edges are tenant-safe organization relationships
The system SHALL model relationships only between two distinct `ORGANIZATION` Parties in the same tenant using `PARENT_OF`, `INVESTED_IN`, `COMMON_CONTROL` or `BUSINESS_PARTNER`.

#### Scenario: Cross-tenant target id
- **WHEN** a tenant submits another tenant's Party id as the target
- **THEN** the request fails as not found and no relationship is written

#### Scenario: Person target
- **WHEN** either relationship endpoint is a PERSON Party
- **THEN** the request is rejected as an invalid enterprise relationship

### Requirement: Symmetric relationships are canonical
`COMMON_CONTROL` and `BUSINESS_PARTNER` edges SHALL be stored with the lower Party id as source and SHALL be returned consistently from either endpoint. Only one active canonical edge of the same type SHALL exist.

#### Scenario: Reverse duplicate
- **WHEN** the same symmetric relationship is submitted with endpoints reversed
- **THEN** the system returns the existing relationship or an explicit duplicate conflict without adding a row

### Requirement: Hierarchical relationships prevent cycles
`PARENT_OF` SHALL reject self-links and any active edge that creates a directed cycle. Concurrent hierarchy changes SHALL be serialized per tenant so that two racing requests cannot together create a cycle.

#### Scenario: Three-node cycle
- **WHEN** A is parent of B and B is parent of C and a caller adds C parent of A
- **THEN** the request returns a conflict and the existing hierarchy remains unchanged

#### Scenario: Concurrent reciprocal parents
- **WHEN** A→B and B→A are submitted concurrently in PostgreSQL
- **THEN** at most one edge becomes active and the final graph is acyclic

### Requirement: Relationship ownership and source metadata are bounded
Directional investment relationships MAY carry an ownership percentage from 0 through 100. Every edge SHALL record source type, safe source reference, optional evidence attachment, start date, creator and audit metadata; unknown fields and out-of-range ownership SHALL be rejected.

#### Scenario: Invalid ownership percentage
- **WHEN** ownership percentage exceeds 100
- **THEN** the request is rejected without an edge

### Requirement: Relationships end without deletion
Normal application flows SHALL end a relationship by setting status `ENDED`, end time and reason with optimistic concurrency; they SHALL NOT physically delete history.

#### Scenario: End active relationship
- **WHEN** an authorized user ends an active edge with its current lock version
- **THEN** the edge becomes ENDED, remains queryable in history and an audit entry is committed
