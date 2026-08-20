## ADDED Requirements

### Requirement: Permission-aware staff and tenant workspace
The PC application SHALL expose `/engagement` policy, service, activity, and announcement views according to server-authorized capabilities and SHALL use separate staff and tenant-principal API projections.

#### Scenario: Tenant principal opens engagement
- **WHEN** a tenant-principal user opens the workspace
- **THEN** it sees only its Party and park-visible matches, requests, registrations, and announcements without staff-only audience, provider, assignment, or audit controls

### Requirement: Real operational data and truth labels
The workspace SHALL load catalogue, lifecycle, capacity, delivery, read, and metric data from mounted APIs and SHALL clearly label official/external eligibility, provider, payment, notification, migration, and mini-program capabilities that are not connected.

#### Scenario: External service is unavailable
- **WHEN** a service depends on an unconnected provider
- **THEN** the workspace shows the provider boundary and does not fabricate booking, fulfillment, payment, or success data

### Requirement: Governed actions and recoverable conflicts
The workspace SHALL use drawers or dialogs for publication, request, registration, check-in, result, and feedback actions, confirm high-risk transitions, and preserve user input across validation, 403, 409, offline, and retry states.

#### Scenario: Registration capacity conflict
- **WHEN** registration returns a concurrent capacity conflict
- **THEN** the UI retains context, explains confirmed or waitlist truth, and can reload the current activity before retry

### Requirement: Responsive and accessible engagement experience
At desktop, 820px, and 390px widths, the workspace SHALL avoid body overflow, render dense content as readable tables or cards, expose state through text in addition to color, and provide loading, empty, permission, expired, withdrawn, offline, and retry states.

#### Scenario: Mobile offline announcement read
- **WHEN** a 390px tenant view loses connectivity while acknowledging an announcement
- **THEN** the content remains readable, no false read success appears, and the action can be retried after reconnection
