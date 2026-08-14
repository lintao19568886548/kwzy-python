## ADDED Requirements

### Requirement: Device workspace uses live governed data
The PC workspace SHALL load live tenant/park-scoped device data and provide permission-gated registration, edit, history and retirement actions. It SHALL show type, location, criticality, status, upcoming inspection and active alarm facts without local fixture records.

#### Scenario: Device version conflict
- **WHEN** an edit returns 409
- **THEN** the drawer preserves entered values and offers reload before retry

### Requirement: Inspection workspace completes the weekly journey
The workspace SHALL expose template publication, schedule activation, task generation, assignment, start, typed checklist submission, exception and linked WorkOrder drill-down using real APIs.

#### Scenario: Critical checklist failure
- **WHEN** an operator submits a critical failed item
- **THEN** the task shows FAILED and the exception links to the one created WorkOrder

### Requirement: Alarm workspace exposes source and action truth
Alarm queue/detail SHALL show canonical severity, occurrence count, provider/binding truth, source-event timeline, acknowledgement/escalation/closure and linked WorkOrder. Color SHALL not be the only severity/status signal.

#### Scenario: Correlated critical alarm
- **WHEN** a second source event correlates to an open alarm
- **THEN** the same detail updates occurrence count and retains both source events

### Requirement: Responsive and failure states preserve work
At 1440, 820 and 390 pixel widths, lists and drawers SHALL avoid body overflow and preserve input across loading, empty, 403, 409, offline and retry states. Dense rows SHALL become readable cards or bounded local scrolling regions.

#### Scenario: Mobile-width inspection offline
- **WHEN** checklist submission fails offline at 390 pixels
- **THEN** entered results remain visible and populated for retry
