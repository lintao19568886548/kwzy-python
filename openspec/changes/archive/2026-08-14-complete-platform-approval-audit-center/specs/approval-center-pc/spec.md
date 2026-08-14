## ADDED Requirements

### Requirement: Unified live approval workspace
The PC approval center SHALL use live APIs for my applications, pending tasks, processed tasks and authorized all-instances views, with filters for status, business type, park, priority and time.

#### Scenario: Pending task decision journey
- **WHEN** an approver opens a pending task, reviews its safe snapshot and timeline, then approves with an idempotency key
- **THEN** the refreshed workspace reflects the committed next step or terminal state without local fixture state

#### Scenario: Applicant sees return and resubmits
- **WHEN** an applicant opens a returned application
- **THEN** the workspace shows the return reason and permits resubmission only for that applicant

### Requirement: Definition administration and timeline drawer
Authorized administrators SHALL create drafts, edit steps, publish and retire definitions from the PC workspace, and users SHALL inspect approval details, current tasks and immutable events in a drawer without navigating away from their filtered list.

#### Scenario: Published definition is read-only
- **WHEN** an administrator opens a published version
- **THEN** its steps are read-only and editing begins in a separate draft version

#### Scenario: Conflict preserves context
- **WHEN** publication or decision returns HTTP 409
- **THEN** the drawer preserves input, shows the conflict and offers reload without displaying false success

### Requirement: Permission, failure and responsive states
The PC approval center SHALL present explicit loading, empty, read-only, 403, 409, error/retry and offline states and SHALL remain keyboard-operable without clipped actions at desktop, tablet and mobile widths.

#### Scenario: Read-only user
- **WHEN** a user has approval read permission but no decision or definition-write permission
- **THEN** lists and timelines remain visible while mutation controls are unavailable

#### Scenario: Mobile retry
- **WHEN** an initial API request fails at mobile width and then succeeds
- **THEN** the page exposes retry, restores live data and has no horizontal body overflow
