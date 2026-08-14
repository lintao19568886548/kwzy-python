# party-enterprise-tags Specification

## Purpose
TBD - created by archiving change complete-party-enterprise-profile.

## Requirements

### Requirement: Enterprise tags retain type and provenance
An enterprise tag SHALL have a normalized name, bounded type `INDUSTRY/CAPABILITY/QUALIFICATION/INTENT/CUSTOM`, source `MANUAL/MIGRATION/EXTERNAL`, confidence from 0 through 1, verification state, creator and timestamps.

#### Scenario: External tag is unverified
- **WHEN** an EXTERNAL tag is received without proven provider review
- **THEN** it is stored as UNVERIFIED and is not presented as a verified fact

### Requirement: Active tag names are unique per Party and type
Only one active tag with the same normalized name and type SHALL exist for a Party. Duplicate submissions SHALL be idempotent by request key or return an explicit conflict without duplicate rows.

#### Scenario: Concurrent duplicate tag
- **WHEN** two requests concurrently create the same normalized active tag
- **THEN** PostgreSQL contains one active tag and both outcomes are deterministic

### Requirement: Tags use lifecycle transitions
Tags SHALL be deactivated with reason and optimistic concurrency rather than physically deleted. A deactivated tag MAY be re-added as a new historical row only through an explicit new request.

#### Scenario: Deactivate tag
- **WHEN** an authorized user deactivates a current tag
- **THEN** it no longer appears in the active list but remains in history and audit

### Requirement: Tags do not grant access or make automated decisions
Enterprise tags SHALL be descriptive metadata only and SHALL NOT expand park scope, permissions, blacklist state, approval outcome, lease eligibility or AI decision authority.

#### Scenario: Forged qualification tag
- **WHEN** a caller adds a qualification tag
- **THEN** no authorization, approval or contract state changes as a side effect
