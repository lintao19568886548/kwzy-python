# spatial-hierarchy-management Specification

## Purpose
TBD - created by archiving change implement-asset-rent-control-v2. Update Purpose after archive.
## Requirements
### Requirement: Typed spatial hierarchy
The system SHALL model park-owned spatial nodes with types `AREA`, `BUILDING`, and `FLOOR`. An AREA MAY be a park root child, a BUILDING MAY belong to a park or AREA, and a FLOOR MUST belong to a BUILDING. Every node SHALL belong to exactly one tenant and park.

#### Scenario: Valid building and floor are created
- **WHEN** an authorized user creates a BUILDING under an AREA and a FLOOR under that BUILDING in the same park
- **THEN** the system persists both nodes and returns their parent and type information

#### Scenario: Invalid parent type is rejected
- **WHEN** a user attempts to create a FLOOR under an AREA or a node under another tenant's park
- **THEN** the system rejects the write without creating a partial hierarchy

### Requirement: Stable codes and acyclic tree
Active spatial-node codes SHALL be unique among siblings within a park, and parent updates MUST NOT create self-reference or any ancestor cycle.

#### Scenario: Duplicate sibling code is rejected
- **WHEN** two active children of one parent use the same normalized code
- **THEN** exactly one write succeeds and the other returns a stable conflict response

#### Scenario: Parent cycle is rejected
- **WHEN** a node is moved below one of its descendants
- **THEN** the system rejects the update and preserves the previous tree

### Requirement: Protected spatial lifecycle
Spatial nodes SHALL support ACTIVE and INACTIVE lifecycle states. The system MUST reject deactivation or deletion when an active descendant unit or effective lease occupancy depends on the node.

#### Scenario: Occupied hierarchy cannot be deactivated
- **WHEN** an authorized user deactivates a building containing an effectively occupied unit
- **THEN** the system returns a business conflict and leaves the hierarchy active

### Requirement: Spatial writes are scoped and audited
Every hierarchy query and write SHALL enforce tenant and park scope. Successful create, move, update and deactivate operations SHALL write transaction-bound audit evidence without sensitive attribute values.

#### Scenario: Out-of-scope hierarchy is invisible
- **WHEN** a LIST-scoped user requests a spatial tree for an unlisted park
- **THEN** the request is denied or returns no resource and no foreign node metadata leaks
