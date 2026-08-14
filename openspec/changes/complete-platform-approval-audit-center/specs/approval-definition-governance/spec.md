## ADDED Requirements

### Requirement: Tenant-scoped workflow definitions
The system SHALL maintain approval definitions with tenant-local unique codes, business type, optional park applicability, status and description; every referenced park, role and user SHALL belong to the request tenant.

#### Scenario: Cross-tenant assignee rejected
- **WHEN** an administrator adds a step referencing a role or user from another tenant
- **THEN** the system returns a non-enumerating validation failure and persists no definition version

#### Scenario: Scoped definition visibility
- **WHEN** a LIST-scoped administrator queries definitions
- **THEN** the result contains only tenant-wide definitions and definitions for accessible parks

### Requirement: Immutable published versions
The system SHALL publish immutable numbered definition versions; editing a published definition SHALL create or update a separate draft, and existing approval instances SHALL remain bound to their submitted version.

#### Scenario: New version does not rewrite running instance
- **WHEN** version 2 is published while an instance is pending on version 1
- **THEN** the pending instance and its task candidates continue to use version 1

#### Scenario: Concurrent publication has one winner
- **WHEN** two transactions publish a draft from the same expected definition version
- **THEN** at most one publication commits and the loser receives HTTP 409

### Requirement: Valid ordered approval steps
Each publishable version SHALL contain contiguous ordered steps with `ANY` or `ALL` mode, at least one same-tenant user or role assignee per step, a valid minimum-approval count, and a positive SLA duration.

#### Scenario: Empty or impossible step rejected
- **WHEN** a draft has no steps, a gap in order, no assignee, or a minimum approval count greater than its candidates
- **THEN** publication is rejected with field-level validation details

#### Scenario: Retired definition blocks new submissions
- **WHEN** the only matching definition is retired
- **THEN** a new generic approval submission fails closed while historical instances remain readable
