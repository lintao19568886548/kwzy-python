# event-outbox-delivery Specification

## Purpose

Define transactional business-event capture, idempotent consumer delivery and controlled dead-letter recovery.

## Requirements

### Requirement: Transactional registered event capture
The system SHALL append a bounded schema-versioned business event in the same transaction as its source mutation, and SHALL reject unregistered event types or oversized payloads.

#### Scenario: Source transaction rolls back
- **WHEN** a business mutation and its event append are rolled back
- **THEN** neither the source change nor the event is dispatchable

#### Scenario: Unregistered event
- **WHEN** a caller emits an event type outside the registry
- **THEN** the command fails without persisting an event

### Requirement: Idempotent consumer delivery
The system SHALL claim pending events concurrently without duplicate ownership and SHALL persist one consumer result per tenant, event and consumer.

#### Scenario: Concurrent dispatchers
- **WHEN** two dispatchers claim the same pending batch on PostgreSQL
- **THEN** each event/consumer pair is executed by at most one dispatcher at that time

#### Scenario: Repeated dispatch
- **WHEN** an already successful event/consumer pair is dispatched again
- **THEN** the stored successful result is returned without repeating side effects

### Requirement: Bounded retry and dead-letter recovery
The system SHALL apply bounded retry with next-attempt time, move exhausted consumers to DEAD, and require an audited authorized command to replay a dead letter as a new attempt generation.

#### Scenario: Consumer repeatedly fails
- **WHEN** failures reach the configured maximum attempts
- **THEN** the consumer log becomes DEAD and is excluded from ordinary dispatch

#### Scenario: Authorized replay
- **WHEN** an operator with replay permission replays a DEAD consumer
- **THEN** a new pending generation is created without deleting the failed evidence

### Requirement: Scoped event operations
The system SHALL enforce tenant, park and permission boundaries for event/dead-letter queries and mutation commands.

#### Scenario: Cross-tenant event id
- **WHEN** a caller supplies an event or consumer id from another tenant
- **THEN** the system returns not found and exposes no metadata
