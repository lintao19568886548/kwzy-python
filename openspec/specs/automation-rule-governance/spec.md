# automation-rule-governance Specification

## Purpose

Define safe, versioned, deterministic and scoped automation-rule governance.

## Requirements

### Requirement: Versioned rule lifecycle
The system SHALL support draft, publish, new-draft and retire operations with optimistic concurrency, immutable published versions and tenant-unique rule codes.

#### Scenario: Publish valid draft
- **WHEN** an authorized administrator publishes a valid draft using its current version
- **THEN** the version becomes immutable and is selected for later matching events

#### Scenario: Stale publication
- **WHEN** two administrators publish using the same prior lock version
- **THEN** one succeeds and the stale command receives 409

### Requirement: Safe deterministic rule grammar
The system SHALL allow only registered event types, allow-listed payload fields/comparators, AND-combined scalar conditions and allow-listed bounded actions, and SHALL reject script, SQL, URL or executable content.

#### Scenario: Unsafe expression
- **WHEN** a rule includes a script, dynamic SQL, URL action or unregistered payload field
- **THEN** publication fails with a validation error

#### Scenario: Deterministic match
- **WHEN** a registered event satisfies every published condition
- **THEN** actions execute in stored order with bounded escaped interpolation

### Requirement: Idempotent traceable executions
The system SHALL record a matched/not-matched/failed execution for each event and published rule version and SHALL make every resulting action idempotent.

#### Scenario: Event replay
- **WHEN** the same event is consumed repeatedly by the rule engine
- **THEN** only one execution and one copy of each action result exists

### Requirement: Scoped rule administration
The system SHALL enforce separate read/write permissions and tenant/park scope for rule definitions, versions, executions and replay operations.

#### Scenario: Read-only administrator
- **WHEN** a caller has rule read permission but not write permission
- **THEN** published definitions and executions are visible but mutation commands return 403
