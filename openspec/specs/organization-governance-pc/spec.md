# organization-governance-pc Specification

## Purpose
Define the operable, permission-consistent and responsive PC organization-governance workspace.

## Requirements

### Requirement: Operable organization governance workspace
The PC system administration experience SHALL let an authorized administrator create and manage groups, regions, park assignments, positions, user assignments, and field policies using live backend APIs.

#### Scenario: Complete hierarchy and assignment journey
- **WHEN** an administrator creates a group, creates a region, assigns a park, creates a position, and assigns a user
- **THEN** each committed change appears after API reload with no local fixture or page-only state

#### Scenario: Field policy changes real user response
- **WHEN** an administrator saves a phone masking policy and reloads the user list as the governed role
- **THEN** the UI displays the server-projected masked value rather than a client-computed substitute

### Requirement: Permission-consistent controls and states
The PC workspace SHALL hide or disable unauthorized mutations and SHALL present explicit loading, empty, permission, conflict, error, and retry states without reporting a failed command as successful.

#### Scenario: Read-only operator
- **WHEN** an operator has organization governance read permission but no write permission
- **THEN** data remains visible while mutation controls are unavailable

#### Scenario: Conflict can be recovered
- **WHEN** a reassignment or primary-position command returns HTTP 409
- **THEN** the workspace shows the conflict, preserves user context, and offers reload/retry without a false success toast

### Requirement: Responsive and accessible administration
The workspace SHALL remain operable at desktop, tablet, and mobile widths with keyboard focus, labelled controls, readable tables, and horizontal overflow rather than clipped content.

#### Scenario: Tablet and narrow viewport
- **WHEN** the workspace is used at tablet or mobile viewport width
- **THEN** forms collapse to one column and tables remain scrollable without overlapping actions
