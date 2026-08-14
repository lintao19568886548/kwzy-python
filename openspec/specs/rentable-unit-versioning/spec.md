# rentable-unit-versioning Specification

## Purpose
TBD - created by archiving change implement-asset-rent-control-v2. Update Purpose after archive.
## Requirements
### Requirement: Effective rentable-unit versions
Each rentable unit SHALL have a stable logical identifier, a positive version number, validity timestamps, an exact published asset-template version and at most one current version. Structural fields include park, spatial node, code, rentable area, template, template-governed attributes and usage type; changing a structural field SHALL create a new version instead of overwriting the current row.

#### Scenario: Structural update creates history
- **WHEN** an authorized user changes the rentable area or template-governed attributes of a vacant current unit with the expected version
- **THEN** the old version retains its template facts and validity end, and a validated new current version is created

### Requirement: Occupancy projection is authoritative
`used_area` SHALL be derived from effective lease occupancy and MUST NOT be accepted from client create/update/version/split/merge payloads. Available area SHALL equal rentable area minus used area and MUST NOT become negative.

#### Scenario: Client tries to write used area
- **WHEN** a client includes `used_area` in a unit mutation payload
- **THEN** validation rejects the field or ignores it without changing the occupancy projection

### Requirement: Controlled unit split
The system SHALL split only a current, vacant, unreserved unit with zero effective occupancy. A split SHALL retire the source version, create two or more validated target units whose areas exactly reconcile to the source area, retain or explicitly select published template versions, and persist source-to-target lineage atomically.

#### Scenario: Vacant unit is split
- **WHEN** an authorized user splits a 100 square metre vacant unit into 40 and 60 square metre targets
- **THEN** the source becomes historical, both targets become current, and lineage plus area reconciliation are queryable

#### Scenario: Occupied unit split is rejected
- **WHEN** any effective lease occupancy exists for the source unit
- **THEN** the split fails atomically with no new units or lineage rows

#### Scenario: Template retained through split
- **WHEN** an authorized user splits a valid warehouse unit without selecting target templates
- **THEN** every target binds the same warehouse template version and copies only valid source attributes

### Requirement: Controlled unit merge
The system SHALL merge two or more current vacant units only when they belong to the same tenant, park and compatible spatial node. A merge SHALL retire all sources, create one validated current target with reconciled area and a compatible published template version, and persist all source-to-target lineage atomically.

#### Scenario: Compatible vacant units are merged
- **WHEN** two compatible vacant units of 40 and 60 square metres are merged
- **THEN** one 100 square metre target is created and both sources remain available as history

#### Scenario: Incompatible template merge
- **WHEN** source units use different template versions and no valid explicit target template is supplied
- **THEN** the merge fails atomically without retiring any source

### Requirement: Optimistic concurrency
Unit version, split and merge commands SHALL require the caller's expected version and SHALL serialize conflicting PostgreSQL writes so that stale or concurrent mutations return a stable 409 response.

#### Scenario: Stale version loses
- **WHEN** two requests mutate the same current unit using the same expected version
- **THEN** only one commits and the other returns a version-conflict response
