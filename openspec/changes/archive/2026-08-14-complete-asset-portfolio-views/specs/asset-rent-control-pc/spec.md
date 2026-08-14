## ADDED Requirements

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
