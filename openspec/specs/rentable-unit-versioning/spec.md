# rentable-unit-versioning Specification

## Purpose
TBD - created by archiving change implement-asset-rent-control-v2. Update Purpose after archive.
## Requirements
### Requirement: Effective rentable-unit versions
Each rentable unit SHALL have a stable logical identifier, a positive version number, validity timestamps and at most one current version. Structural fields include park, spatial node, code, rentable area and usage type; changing a structural field SHALL create a new version instead of overwriting the current row.

#### Scenario: Structural update creates history
- **WHEN** an authorized user changes the rentable area of a vacant current unit with the expected version
- **THEN** the old version receives a validity end and a new current version is created with an incremented version number

### Requirement: Occupancy projection is authoritative
`used_area` SHALL be derived from effective lease occupancy and MUST NOT be accepted from client create/update/version/split/merge payloads. Available area SHALL equal rentable area minus used area and MUST NOT become negative.

#### Scenario: Client tries to write used area
- **WHEN** a client includes `used_area` in a unit mutation payload
- **THEN** validation rejects the field or ignores it without changing the occupancy projection

### Requirement: Controlled unit split
The system SHALL split only a current, vacant, unreserved unit with zero effective occupancy. A split SHALL retire the source version, create two or more target units whose areas exactly reconcile to the source area, and persist source-to-target lineage atomically.

#### Scenario: Vacant unit is split
- **WHEN** an authorized user splits a 100 square metre vacant unit into 40 and 60 square metre targets
- **THEN** the source becomes historical, both targets become current, and lineage plus area reconciliation are queryable

#### Scenario: Occupied unit split is rejected
- **WHEN** any effective lease occupancy exists for the source unit
- **THEN** the split fails atomically with no new units or lineage rows

### Requirement: Controlled unit merge
The system SHALL merge two or more current vacant units only when they belong to the same tenant, park and compatible spatial node. A merge SHALL retire all sources, create one current target with reconciled area and persist all source-to-target lineage atomically.

#### Scenario: Compatible vacant units are merged
- **WHEN** two compatible vacant units of 40 and 60 square metres are merged
- **THEN** one 100 square metre target is created and both sources remain available as history

### Requirement: Optimistic concurrency
Unit version, split and merge commands SHALL require the caller's expected version and SHALL serialize conflicting PostgreSQL writes so that stale or concurrent mutations return a stable 409 response.

#### Scenario: Stale version loses
- **WHEN** two requests mutate the same current unit using the same expected version
- **THEN** only one commits and the other returns a version-conflict response
