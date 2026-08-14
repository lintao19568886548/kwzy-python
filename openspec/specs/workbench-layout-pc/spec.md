# workbench-layout-pc Specification

## Purpose

Define permission-safe effective workbench layouts and resilient multi-role PC rendering and editing.

## Requirements

### Requirement: Effective role and user layout
The system SHALL resolve a user's effective workbench from their active user layout, otherwise an authorized role default, otherwise the server default, without granting additional data permissions.

#### Scenario: User has no override
- **WHEN** a user opens the workbench without a saved personal layout
- **THEN** the highest-priority applicable role default or server default is returned

#### Scenario: Widget permission absent
- **WHEN** a configured widget requires a permission the user lacks
- **THEN** the widget is omitted and its data is not queried

### Requirement: Validated optimistic layout editing
The system SHALL allow authorized users to save only registered widgets within grid bounds, reject overlap or unsafe configuration, and require the expected layout version.

#### Scenario: Stale layout save
- **WHEN** two browser sessions save the same layout version
- **THEN** one succeeds and the stale save receives 409 with the server version

#### Scenario: Arbitrary widget URL
- **WHEN** a client submits an unregistered widget or custom data URL
- **THEN** the layout is rejected

### Requirement: Live multi-role PC workbench
The PC SHALL render server-provided cards, todos and notifications with source drill-down and SHALL provide editable/reset behavior only when permitted.

#### Scenario: Operations role journey
- **WHEN** an operations user opens the workbench
- **THEN** only permitted live widgets and park-scoped data are shown with no local JSON fallback

### Requirement: Resilient responsive states
The PC SHALL provide loading, empty, permission/read-only, conflict, offline and retry states on desktop, tablet and mobile widths without clipped controls or unreadable data.

#### Scenario: API unavailable
- **WHEN** a workbench request fails
- **THEN** committed content is not replaced by fake values and an actionable retry state is shown
