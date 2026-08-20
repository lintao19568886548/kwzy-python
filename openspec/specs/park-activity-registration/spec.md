# Park Activity Registration

## Purpose

Define versioned park activities, serialized capacity, waitlists, attendance, and feedback evidence.

## Requirements

### Requirement: Immutable approved activity publication
The system SHALL keep editable activity drafts and publish only a native-approved immutable version containing park, schedule, location, audience, registration window, capacity, attendee rules, attachments, and cancellation terms.

#### Scenario: Change capacity after publication
- **WHEN** an organizer changes capacity or schedule after a version is published
- **THEN** a new version requires approval and existing registrations remain bound to the version they accepted

### Requirement: Concurrency-safe registration and waitlist
The system SHALL bind registration to the tenant principal's persisted Party and visible park, enforce one active registration per Party and version, and serialize capacity so excess requests enter an ordered waitlist without overbooking.

#### Scenario: Last-seat race
- **WHEN** concurrent eligible Parties request the final available place
- **THEN** at most one receives confirmed capacity and the other receives a deterministic waitlist or full result

### Requirement: Idempotent cancellation and promotion
The system SHALL cancel a registration with append-only evidence, release capacity once, and promote the next eligible waitlist entry transactionally and idempotently.

#### Scenario: Replay cancellation
- **WHEN** a confirmed registration cancellation is retried with the same command fingerprint
- **THEN** capacity is released once and no second waitlist promotion occurs

### Requirement: Check-in, completion, and feedback evidence
The system SHALL record authorized check-in evidence against a confirmed registration, close or cancel the activity through valid transitions, and accept at most one feedback record from an attended Party.

#### Scenario: Feedback without attendance
- **WHEN** a Party that lacks completed check-in attempts to submit activity feedback
- **THEN** the system rejects the request without adding feedback or altering attendance evidence
