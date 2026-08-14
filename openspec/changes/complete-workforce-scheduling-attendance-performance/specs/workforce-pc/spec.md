## ADDED Requirements

### Requirement: Workspace is live and role aware
The PC workspace SHALL use authenticated APIs, expose only permitted actions and contain no fixture-only success path.

#### Scenario: Read-only role
- **WHEN** a user has read but no manage/review permission
- **THEN** live data is visible and mutations are unavailable with reason

### Requirement: Responsive and failure complete
The workspace SHALL remain usable at desktop/tablet/mobile widths with loading, empty, forbidden, conflict, offline and retry states and no body overflow.

#### Scenario: Mobile offline recovery
- **WHEN** API fails then recovers on mobile
- **THEN** retry restores live content without reload
