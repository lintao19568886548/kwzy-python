# asset-rent-control-pc Specification

## Purpose
TBD - created by archiving change implement-asset-rent-control-v2. Update Purpose after archive.
## Requirements
### Requirement: Unified spatial and rent-control workspace
The PC application SHALL provide a park selector, spatial tree, status/usage filters, summary cards and switchable matrix/list inventory views backed by real APIs. It MUST NOT require manual entry of internal park or spatial IDs.

#### Scenario: Operator changes park
- **WHEN** an operator selects another authorized park
- **THEN** the spatial tree, metrics and unit inventory reload for that park and preserve valid filters

### Requirement: Actionable unit detail
Selecting a unit SHALL open an operational detail surface with core attributes, availability, current lease/Party summary, version history and lineage. Authorized actions SHALL include create/edit, status change, versioned structural update, split and merge; unavailable actions SHALL explain the blocking reason.

#### Scenario: Occupied split action is blocked
- **WHEN** an occupied unit is selected
- **THEN** the split action is disabled or rejected with an understandable occupancy reason while read-only detail remains available

### Requirement: Permission-consistent controls
Route visibility and buttons SHALL reflect action permissions, while the API independently enforces action and park scope. Direct navigation or crafted requests MUST NOT bypass the server.

#### Scenario: Read-only operator
- **WHEN** a user has `unit:read` but not `unit:write`
- **THEN** inventory and detail are usable, mutation controls are absent, and direct mutation API requests return 403

### Requirement: Responsive and accessible operation
The workspace SHALL remain usable at desktop and tablet widths, expose visible focus, semantic labels and keyboard-reachable view/filter/action controls, and provide loading, empty, error, forbidden and success states.

#### Scenario: Tablet keyboard flow
- **WHEN** a keyboard user operates the page at tablet width
- **THEN** park selection, tree, filters, view toggle, unit selection and permitted primary actions are reachable without horizontal page overflow

### Requirement: Complete rent-control multi-view workspace
The PC workspace SHALL switch among matrix, map, list, vacancy, expiry and analysis views backed by scoped live APIs while preserving compatible park, subtree and asset filters.

#### Scenario: Operator moves from matrix to analysis
- **WHEN** an operator changes view with active park and subtree filters
- **THEN** the analysis reloads from the same scope and reconciles to the inventory summary

### Requirement: Truthful accessible map state
The map view SHALL render only stored geometry as keyboard-reachable features, label its coordinate reference/provider state and expose unmapped inventory without fabricated locations.

#### Scenario: No mapped spaces
- **WHEN** a park has inventory but no geometry
- **THEN** the map shows an actionable unmapped state and does not display placeholder pins

### Requirement: Template-aware unit administration
Authorized users SHALL select a published asset template and edit its typed dynamic fields when creating or structurally versioning a unit, while read-only users can inspect template facts without mutation controls.

#### Scenario: Required template field omitted
- **WHEN** a user submits a unit form without a required dynamic field
- **THEN** the UI retains input and displays the server validation error without reporting success

### Requirement: Resilient responsive multi-view states
Template, map, vacancy, expiry and analysis surfaces SHALL provide loading, empty, forbidden, conflict, offline and retry states on desktop, tablet and mobile widths without horizontal body overflow.

#### Scenario: Analysis request offline
- **WHEN** the analysis API is unavailable after committed data was shown
- **THEN** no fake metrics replace committed values and the user receives a retry action
