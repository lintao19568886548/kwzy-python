## ADDED Requirements

### Requirement: Server-controlled initial assignment
Lead creation SHALL ignore client-declared permission or ownership authority and, when an effective rule applies to the source trigger, assign through that immutable rule version in the same transaction as creation.

#### Scenario: Manual lead uses automatic rule
- **WHEN** an authorized user creates a Lead with auto assignment enabled for MANUAL_CREATE
- **THEN** the server selects an eligible owner, stores the rule/version evidence and opens the owner's follow-up work item atomically

#### Scenario: No rule applies
- **WHEN** a Lead source has no effective assignment rule and no authorized explicit owner
- **THEN** the Lead enters the public pool without inventing an owner

### Requirement: Channel source provenance
Channel-originated Leads SHALL retain a bounded source type, stable source reference and receive-event linkage without storing unverifiable raw payloads in the Lead aggregate.

#### Scenario: Accepted channel event
- **WHEN** a signed event is normalized into a Lead
- **THEN** the Lead can be traced to one inbox event and repeat processing returns the same source reference
