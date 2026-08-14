## MODIFIED Requirements

### Requirement: Effective rentable-unit versions
Each rentable unit SHALL have a stable logical identifier, a positive version number, validity timestamps, an exact published asset-template version and at most one current version. Structural fields include park, spatial node, code, rentable area, template, template-governed attributes and usage type; changing a structural field SHALL create a new version instead of overwriting the current row.

#### Scenario: Structural update creates history
- **WHEN** an authorized user changes the rentable area or template-governed attributes of a vacant current unit with the expected version
- **THEN** the old version retains its template facts and validity end, and a validated new current version is created

### Requirement: Controlled unit split
The system SHALL split only a current, vacant, unreserved unit with zero effective occupancy. A split SHALL retire the source version, create two or more validated target units whose areas exactly reconcile to the source area, retain or explicitly select published template versions, and persist source-to-target lineage atomically.

#### Scenario: Template retained through split
- **WHEN** an authorized user splits a valid warehouse unit without selecting target templates
- **THEN** every target binds the same warehouse template version and copies only valid source attributes

### Requirement: Controlled unit merge
The system SHALL merge two or more current vacant units only when they belong to the same tenant, park and compatible spatial node. A merge SHALL retire all sources, create one validated current target with reconciled area and a compatible published template version, and persist all source-to-target lineage atomically.

#### Scenario: Incompatible template merge
- **WHEN** source units use different template versions and no valid explicit target template is supplied
- **THEN** the merge fails atomically without retiring any source
