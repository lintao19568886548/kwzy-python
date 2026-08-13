## ADDED Requirements

### Requirement: Contract workspace and real selectors
PC `/leases` MUST provide KPI cards, park/Party/status/type/expiry/approval/change filters, list and expiry views, and authorized Park, eligible Party and current Unit selectors. The primary workflow MUST NOT require users to type park, Party, Unit, contract, approval or settlement internal ids.

#### Scenario: Create multi-unit contract
- **WHEN** a lease writer selects an authorized park, Party, multiple Units, dates and charge rules
- **THEN** the page previews occupancy and schedules, validates visible errors, creates a DRAFT and opens its detail without losing selections

#### Scenario: Selector has no eligible rows
- **WHEN** an authorized park has no eligible Party or Unit
- **THEN** the form shows a specific empty state and disables submission instead of accepting `0` or arbitrary ids

### Requirement: Versioned contract detail and actions
Contract detail MUST show current header, Party, units, charges/schedules, immutable versions/diff, change and approval timeline, documents/signature readiness, work items and exit settlement. Available actions MUST follow status, ownership, expected version and permission rules.

#### Scenario: Approve and activate
- **WHEN** a different authorized approver opens a pending contract with an approved main document
- **THEN** they can approve, see PENDING_ACTIVE, activate and observe version 1, occupancy and timeline update without manual refresh ambiguity

#### Scenario: Create price change
- **WHEN** a lease changer creates a future aligned price adjustment
- **THEN** the detail shows before/after charge and schedule diff, submission/approval state and eventual applied version

#### Scenario: Exit settlement close
- **WHEN** an authorized user completes handover, item, approval and clearance evidence gates
- **THEN** detail clearly distinguishes recorded clearance from actual external money movement and confirms terminal version/Unit release after close

### Requirement: Permission-consistent and recoverable states
PC MUST implement loading, empty, validation, forbidden, read-only, backend error, success, stale 409, occupancy conflict and recoverable 503 states. UI permission hints MUST match ownership/status while server authorization remains final, and asynchronous feedback MUST not be overwritten by an older request or timer.

#### Scenario: Read-only lease user
- **WHEN** a user has `lease:read` without write/change/approve/document/settle permissions
- **THEN** they can navigate authorized summary/detail/version data but all mutating controls are unavailable and direct writes return 403

#### Scenario: Stale change form
- **WHEN** submit returns `LEASE_VERSION_CONFLICT` 409
- **THEN** the page preserves the user's draft, displays the latest contract/version summary and offers explicit refresh/rebase rather than overwriting data

#### Scenario: Signing provider unavailable
- **WHEN** a signature request returns the fail-closed 503 code
- **THEN** the document panel retains context, labels signing NOT_LIVE and offers retry/configuration guidance without marking SIGNED

### Requirement: Responsive and accessible interaction
The workspace MUST have no page-level horizontal overflow at supported desktop and 768px tablet widths, use semantic labels and dialogs, preserve visible focus, expose status text beyond color, and provide a complete keyboard path through filters, list, detail tabs and allowed actions.

#### Scenario: Tablet keyboard journey
- **WHEN** a keyboard user at 768px opens contracts, filters, selects a row, inspects versions and closes detail
- **THEN** every step is reachable in logical order with visible focus and no hidden action behind hover-only controls

#### Scenario: Validation announcement
- **WHEN** schedule or settlement validation fails
- **THEN** the summary and field errors are programmatically associated and focus moves to the first actionable problem

### Requirement: Browser acceptance matrix
Playwright MUST cover create/preview/submit/approve/document/activate, change apply, exit close, read-only denial, stale conflict, recoverable provider/backend failure and tablet keyboard journeys with no skips against PostgreSQL-backed full stack.

#### Scenario: Full contract journey
- **WHEN** the local full-stack E2E suite runs from a fresh migrated database
- **THEN** the contract lifecycle scenarios pass without mocked browser network success and reconcile API/PC state
