## ADDED Requirements

### Requirement: Versioned park assignment rules
The system SHALL maintain tenant- and park-scoped assignment rules with optimistic locking, immutable published versions and at most one effective version per trigger.

#### Scenario: Publish a valid rule
- **WHEN** an authorized administrator publishes a draft whose members are active and park-authorized
- **THEN** the immutable version becomes effective for its configured triggers without changing prior Lead history

#### Scenario: Stale rule update
- **WHEN** two administrators update one draft using the same expected version
- **THEN** one succeeds and the stale command receives 409

### Requirement: Bounded eligible members
Each published rule SHALL contain a bounded ordered member set with positive capacity and optional weight, and execution MUST exclude inactive users, cross-tenant users and users without current park scope.

#### Scenario: Member park grant revoked
- **WHEN** a configured member no longer has access to the rule park
- **THEN** preview and execution exclude that member without assigning the Lead out of scope

### Requirement: Deterministic capacity-aware selection
Automatic assignment SHALL select an eligible member using current open workload relative to capacity, then last assignment time, stable member order and user id, under PostgreSQL serialization.

#### Scenario: Concurrent automatic assignment
- **WHEN** multiple workers assign new Leads against the same published version concurrently
- **THEN** every Lead receives at most one owner and each result has exactly one matching assignment event

### Requirement: Explainable preview and fallback
Authorized users SHALL be able to preview eligible members, workload, capacity, exclusion reasons and the deterministic winner without mutation; execution with no eligible member SHALL place the Lead in the public pool and record a stable fallback reason.

#### Scenario: All members at capacity
- **WHEN** every otherwise eligible member has reached configured open-Lead capacity
- **THEN** the Lead remains or becomes PUBLIC and an `AUTO_ASSIGN_FALLBACK` event explains the capacity condition
