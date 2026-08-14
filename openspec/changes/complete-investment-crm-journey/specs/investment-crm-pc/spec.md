## ADDED Requirements

### Requirement: Assignment governance workspace
The PC CRM SHALL expose published/draft assignment rules, bounded member capacity, deterministic preview, publish conflict and manual override history using live scoped APIs.

#### Scenario: Manager previews assignment
- **WHEN** a manager previews a rule for a selected park and source trigger
- **THEN** the page shows eligible workload, exclusions and winner without mutating any Lead

### Requirement: Viewing and intent workflow
Lead detail SHALL provide viewing schedule/status, units and outcomes plus intent draft/version, approval status, approval deep link and approved-lock actions consistent with server permissions.

#### Scenario: Intent awaiting approval
- **WHEN** an owner submits a valid intent
- **THEN** the detail shows PENDING with a deep link to the real approval instance and disables lock until the server reports APPROVED

### Requirement: Channel inbox operations
Channel administrators SHALL see configuration status, local-versus-live verification state, accepted/quarantined receive facts and controlled replay actions without exposing secrets or raw sensitive payloads.

#### Scenario: Quarantined channel event
- **WHEN** a mapped event is quarantined
- **THEN** the UI shows its digest, safe preview and stable reason with retry only for authorized users

### Requirement: Complete CRM responsive states
Assignment, viewing, intent and channel surfaces SHALL support loading, empty, forbidden, conflict, offline and retry states at desktop, tablet and mobile widths without page-level horizontal overflow.

#### Scenario: Offline after committed intent
- **WHEN** the intent API becomes unavailable after committed data was displayed
- **THEN** the UI does not fabricate approval status and offers a clear retry action
