## ADDED Requirements

### Requirement: Staff workspace exposes the real service lifecycle
The PC workspace SHALL load live queue/SLA/timeline data and provide permission-gated intake, dispatch, quote, fulfillment and completion actions. Success messages SHALL follow successful HTTP responses and no local fixture SHALL stand in for records.

#### Scenario: Dispatch conflict
- **WHEN** reassignment returns 409
- **THEN** the drawer preserves the reason and offers reload before retry

### Requirement: Tenant-principal view is Party-limited
For a tenant-principal role, the workspace SHALL call tenant routes only and show its Party's requests, quote decisions, acceptance/rework and rating actions without internal cost/assignment configuration.

#### Scenario: Tenant switches URL id
- **WHEN** the browser navigates to another Party's request id
- **THEN** no foreign data renders and the page shows a non-disclosing denied/not-found state

### Requirement: SLA and quote truth is understandable
Status chips, countdown/breach labels, quote version/total/decision, actual-vs-quote variance and acceptance attempts SHALL be derived from API fields and have accessible text in addition to color.

#### Scenario: Breached urgent request
- **WHEN** an urgent request exceeds response SLA
- **THEN** the queue and detail both show the named breach and original deadline

### Requirement: Responsive/error states preserve work
At 1440, 820 and 390 pixel widths, queue and drawers SHALL avoid body overflow and preserve entered content across loading, 403, 409, offline and retry states. Dense tables SHALL become readable cards or locally scrolling regions.

#### Scenario: Mobile offline completion draft
- **WHEN** completion submission fails offline at 390 pixels
- **THEN** summary/evidence fields remain readable and populated for retry
