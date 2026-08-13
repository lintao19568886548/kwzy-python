## ADDED Requirements

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
