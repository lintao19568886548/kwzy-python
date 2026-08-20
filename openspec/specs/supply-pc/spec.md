# Supply PC Workspace

## Purpose

Define a permission-aware, real-data, governed, responsive, and resilient supply workspace.

## Requirements

### Requirement: Permission-aware supply workspace
The PC application SHALL expose `/supply` overview, supplier, procurement, inventory, and outsourcing views only according to server-authorized capabilities.

#### Scenario: Read-only operator opens workspace
- **WHEN** a user has supply read permission but no mutation permissions
- **THEN** operational data is visible and unauthorized action controls are absent or disabled

### Requirement: Real operational data
The workspace SHALL load KPIs, lists, balances, movements, and lifecycle state from mounted APIs and SHALL not use local JSON, fake success, or static charts.

#### Scenario: API request fails
- **WHEN** an operational query fails
- **THEN** an error state identifies the failed region and offers retry without fabricating values

### Requirement: Governed actions and conflicts
The workspace SHALL use drawers or dialogs for mutations, confirm high-risk receipt/issue/adjustment/acceptance actions, and display validation, permission, idempotency, and concurrency conflicts.

#### Scenario: Stock conflict
- **WHEN** issue fails because concurrent activity consumed availability
- **THEN** the UI retains user context, explains the conflict, and can reload the current balance

### Requirement: Responsive and resilient experience
The workspace SHALL remain usable at desktop, tablet, and 390px widths and SHALL provide loading, empty, permission, offline, retry, and readable table/card states.

#### Scenario: Mobile offline state
- **WHEN** the browser becomes offline at 390px width
- **THEN** the workspace shows an offline banner, prevents unsafe submission, and recovers after reconnection
